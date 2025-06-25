package mongodb_rpc

import (
	"bytes"
	"context"
	"fmt"
	"io"
	"log/slog"
	"net/url"
	"os"
	"os/exec"
	"regexp"
	"runtime"
	"strconv"
	"strings"
	"sync"
	"syscall"
	"time"

	"github.com/pkg/errors"
)

const ClusterTypeReplicaSet = "MongoReplicaSet"

type MongoHost struct {
	ClusterName   string
	Host          string
	Port          int
	UserName      string
	Password      string
	SetName       string
	AdminUsername string
	AdminPassword string
	RealRtxId     string // 真实的RTX ID
}

func encodeURIComponent(str string) string {
	str = url.QueryEscape(str)
	str = strings.Replace(str, "+", "%20", -1)
	return str
}

func (h *MongoHost) Uri() string {
	if h.SetName == "" {
		return fmt.Sprintf("mongodb://%s:%s@%s/test?authSource=admin&appname=webconsole_%s",
			h.UserName, encodeURIComponent(h.Password), h.Host, h.RealRtxId)
	} else {
		// 副本集, replicaSet=SetName不加时，可以直接连Secondary
		return fmt.Sprintf(
			"mongodb://%s:%s@%s/test?authSource=admin&appname=webconsole_%s",
			h.UserName, encodeURIComponent(h.Password), h.Host, h.RealRtxId)
	}
}

// MongoShell is a routine that can be run and stopped.
type MongoShell struct {
	logger        *slog.Logger
	ProcessStdin  *os.File
	ProcessOutBuf []byte
	OutBuf        []byte
	Cmd           string
	BufChan       chan []byte
	Pid           int
	StopChan      chan struct{}
	MongoHost     MongoHost
	MongoVersion  string
	ShellBin      string // mongo or mongosh
	ReadPref      string // primary,secondary,nearest
}

// NewMongoShellFromParm create a new MongoShell instance
func NewMongoShellFromParm(p *QueryParams) *MongoShell {
	setName := ""
	if p.ClusterType == ClusterTypeReplicaSet {
		setName = p.SetName
	}
	return &MongoShell{
		BufChan:      make(chan []byte, 2),
		StopChan:     make(chan struct{}, 1),
		MongoVersion: p.Version,
		MongoHost: MongoHost{
			ClusterName:   p.ClusterDomain,
			Host:          p.Addresses[0], // 只取第一个地址
			UserName:      p.UserName,
			Password:      p.Password,
			SetName:       setName,
			AdminUsername: p.AdminUsername,
			AdminPassword: p.AdminPassword,
			RealRtxId:     p.OaUser,
		},
		ReadPref: p.ReadPreference,
	}
}

// parseMongoVersion parses the MongoDB version string.
func parseMongoVersion(version string) (major, minor int, err error) {
	if strings.Contains(version, "-") {
		fs := strings.Split(version, "-")
		if len(fs) >= 2 {
			version = fs[1]
		} else {
			return 0, 0, fmt.Errorf("invalid version string")
		}
	}
	fs := strings.Split(version, ".")
	if len(fs) < 2 {
		return 0, 0, fmt.Errorf("invalid version string")
	}

	major, err = strconv.Atoi(fs[0])
	if err != nil {
		return 0, 0, fmt.Errorf("invalid major version")
	}
	minor, err = strconv.Atoi(fs[1])
	if err != nil {
		return 0, 0, fmt.Errorf("invalid minor version")
	}
	return
}

// buildArgs builds the arguments for the MongoShell process.
// 不同的版本，shell和参数都不同
func buildArgs(r *MongoShell) (argv []string, err error) {
	_, _, err = parseMongoVersion(r.MongoVersion)
	if err != nil {
		return nil, fmt.Errorf("invalid version string")
	}

	// 4.2 之前的版本，使用 mongo
	// isLowerVersion := major < 4 || (minor < 2 && major == 4)
	isLowerVersion := true // 高版本打算用mongosh的，但搭配mongosh跑不起来. 就先用mongo

	if isLowerVersion {
		r.ShellBin = "mongo"
	} else {
		r.ShellBin = "mongosh"
	}

	evalJs := ""
	isMongos := r.MongoHost.SetName == ""

	/*
		ReadPref:
		- "" 默认 secondary
		- secondary = "secondary" >=3节点
		- secondaryPreferred = "secondaryPreferred" <3节点在primary上执行
	*/

	// r.MongoHost.ClusterName 是集群名称，例如: "x.x.x.x". re.match 小写字母大写字母-_数字 和 .
	reClusterName := regexp.MustCompile("^[a-zA-Z0-9-_.]+$")
	if !reClusterName.MatchString(r.MongoHost.ClusterName) {
		r.MongoHost.ClusterName = "unknown"
	}

	hintJs := "print('connect to " + r.MongoHost.ClusterName + " success. db is ' + db.getName())"

	if r.ReadPref == "secondary" || r.ReadPref == "" {
		if isMongos {
			// 分片集群，总是先执行一次 setReadPref secondary
			evalJs = "db.getMongo().setReadPref('secondary');" + hintJs
		} else {
			// 副本集，4.2 之前的版本，使用 setSlaveOk
			if isLowerVersion {
				evalJs = "db.getMongo().setSecondaryOk(true);" + hintJs
			} else {
				evalJs = "db.getMongo().setReadPref('secondary');" + hintJs
			}
		}
	} else { // secondaryPreferred, < 3节点, 允许在primary上执行

		// 分片集群: setReadPref secondaryPreferred
		if isMongos {
			evalJs = "db.getMongo().setReadPref('secondaryPreferred');" + hintJs
		} else {
			// 副本集: 4.2 之前的版本，使用 setSecondaryOk
			if isLowerVersion {
				evalJs = "if (! db.isMaster().ismaster) {db.getMongo().setSecondaryOk(true);} ;" + hintJs
			} else {
				evalJs = "if (! db.isMaster().ismaster) {db.getMongo().setReadPref('secondary');}; " + hintJs
			}
		}
	}

	cmdPath, err := exec.LookPath(r.ShellBin)
	if err != nil {
		return nil, fmt.Errorf("internal error, exec.LookPath failed")
	}
	argv = append(argv, []string{cmdPath, "--norc", "--quiet", "--eval", evalJs, "--shell", r.MongoHost.Uri()}...)
	return argv, nil
}

// Run starts the MongoShell process.
// 如果返回Error，表示进程启动失败，startWg.Done() 不会被调用
func (r *MongoShell) Run(startWg *sync.WaitGroup, logger *slog.Logger) error {
	r.logger = logger
	r.logger.Info("Run")
	var err error

	var inr, outr, outw *os.File
	inr, r.ProcessStdin, err = os.Pipe()
	if err != nil {
		r.logger.Error("os.Pipe", slog.Any("err", err))
		return fmt.Errorf("internal error, create pipe failed")
	}
	defer r.ProcessStdin.Close()
	defer inr.Close()

	outr, outw, err = os.Pipe()
	if err != nil {
		r.logger.Error("os.Pipe", slog.Any("err", err))
		return fmt.Errorf("internal error, create pipe failed")
	}
	defer outr.Close()
	defer outw.Close()

	r.logger.Info("createMongoShell", slog.Any("MongoHost", r.MongoHost))
	// try to create readonly user

	err = createReadOnlyUser(r.MongoHost.Host, r.MongoHost.AdminUsername, r.MongoHost.AdminPassword,
		r.MongoHost.UserName, r.MongoHost.Password)
	if err != nil {
		if errors.Is(err, ErrConnectFail) {
			r.logger.Error("ErrConnectFail", slog.Any("err", err))
			return fmt.Errorf("internal error, ErrConnectFail")
		} else {
			r.logger.Error("ErrCreateReadOnlyUserFail", slog.Any("err", err))
			return fmt.Errorf("internal error, ErrCreateReadOnlyUserFail")
		}

	}

	// 启动进程，启动后，将进程的Pid出发送到 BufChan
	// 如果进程退出，关闭 BufChan
	pidChan := make(chan int)
	procCtx, procCancel := context.WithCancel(context.Background())
	_ = procCancel

	argv, err := buildArgs(r)
	if err != nil {
		r.logger.Error("buildArgs", slog.Any("err", err))
		return fmt.Errorf("internal error, start process failed")
	}
	r.logger.Info("StartProcess", slog.String("cmdPath", argv[0]), slog.Any("argv", argv))

	go func(pid chan<- int) {
		proc, err := os.StartProcess(argv[0], argv, &os.ProcAttr{
			Files: []*os.File{inr, outw, outw},
		})
		if err != nil {
			r.logger.Error("os.StartProcess", slog.Any("err", err))
		}
		pidChan <- proc.Pid
		// 等待进程结束， 进程结束后，关闭 BufChan
		state, err := proc.Wait()
		r.logger.Info("proc.exited", slog.String("state", state.String()), slog.Any("err", err))

		r.Pid = 0
		procCancel()
		outr.Close()
		r.logger.Info("procCancel")

	}(pidChan)

	pid := <-pidChan
	r.Pid = pid
	time.Sleep(2 * time.Second)
	r.logger.Info("startProcess",
		slog.String("cmdPath", argv[0]), slog.Any("argv", argv),
		slog.Int("pid", r.Pid), slog.Any("err", err))
	startWg.Done() // signal to main goroutine

	wg := sync.WaitGroup{}
	wg.Add(1)
	go func() {
		// read outr -> write BufChan
		r.logger.Info("pumpStdout: always read from outr, and send to BufChan")
		defer wg.Done()
		// var buf = make([]byte, 1024)

		dataChan := make(chan []byte)
		errChan := make(chan error)
		// read from outr background. 这是为了让 outr 的读取不阻塞
		bgreadWg := sync.WaitGroup{}
		bgreadWg.Add(1)
		go func(wg *sync.WaitGroup) {
			defer wg.Done()
			goId := GetGoid()
			r.logger.Info("outr.read background", slog.Int64("goId", goId))
			for {
				buffer := make([]byte, 1024)
				n, err := outr.Read(buffer) // This call is blocking
				r.logger.Info("outr.read background", slog.Int64("goId", goId), slog.Int("n", n), slog.Any("err", err))
				if err != nil && err != io.EOF {
					return
				}
				if n > 0 {
					r.logger.Info("outr.read background send to dataChan", slog.Int64("goId", goId), slog.Int("n", n))
					dataChan <- buffer[:n]
					r.logger.Info("outr.read background send to dataChan done", slog.Int64("goId", goId), slog.Int("n", n))
				}
			}
		}(&bgreadWg)

		for {
			select {
			case data := <-dataChan:
				r.logger.Info("readFromOutr",
					slog.Int("n", len(data)),
					slog.String("data", string(data)))
				r.BufChan <- data
			case <-r.StopChan:
				r.logger.Info("pumpStdout stop, because StopChan", slog.String("pid", strconv.Itoa(r.Pid)))
				err := syscall.Kill(r.Pid, syscall.SIGINT)
				if err != nil {
					r.logger.Error("syscall.Kill", slog.Any("err", err))
				} else {
					r.logger.Info("syscall.Kill success", slog.String("pid", strconv.Itoa(r.Pid)))
				}
			case <-procCtx.Done():
				r.logger.Info("pumpStdout stop, because procCtx.Done")
				// r.BufChan <- []byte("exit\n")
				goto done

			default:
				// default 留空没问题吧
				/*
					// 阻塞读取 outr
					n, readErr := outr.Read(buf)
					r.logger.Info("readFromOutr",
						slog.Int("n", n),
						slog.String("data", string(buf[:n])),
						slog.Any("err", readErr),
					)
					if err != nil {
						r.logger.Error("outr.Read", slog.Any("err", readErr))
						goto done
					}
					if n > 0 {
						// 发送到 BufChan
						r.logger.Info("sendToBufChan", slog.Int("n", n),
							slog.String("data", string(buf[:n])))
						var tmpBuf = make([]byte, n)
						copy(tmpBuf, buf[:n])
						r.BufChan <- tmpBuf
					}
				*/
			}
		}
	done:
		r.logger.Info("bgreadWg.Wait start", slog.String("func", "pumpStdout"))
		bgreadWg.Wait()
		r.logger.Info("bgreadWg.Wait done", slog.String("func", "pumpStdout"))
		r.logger.Info("close chan start", slog.String("func", "pumpStdout"))
		close(dataChan)
		close(errChan)
		close(r.BufChan)
		r.logger.Info("close chan done", slog.String("func", "pumpStdout"))
	}()

	wg.Wait()
	r.logger.Info("pumpStdout is done")
	return nil
}

// ReceiveMsg receives a message from the process
func (r *MongoShell) ReceiveMsg(timeout int64) (out []byte, err error) {
	buf := make([]byte, 0, maxRespSize)
	msg := bytes.NewBuffer(buf)
	ctxTimeout, procTimeout := context.WithTimeout(context.Background(), time.Duration(timeout)*time.Second)
	_ = procTimeout // 暂时不用
	checkCone := time.Tick(100 * time.Millisecond)
	checkConeCount := 0
	bytesTotal := 0
	for {
		select {
		case v, ok := <-r.BufChan:
			r.logger.Info("readFromBufChan", slog.Bool("isResponseEnd", isResponseEnd(v)),
				slog.String("v", string(v)))

			if !ok {
				r.logger.Info("chan closed", slog.String("v", string(v)))
				return msg.Bytes(), fmt.Errorf("chan closed")
			}
			n, werr := msg.Write(v)
			bytesTotal += n
			// 超过了bufSize
			if werr != nil {
				return msg.Bytes(), werr
			}
			if bytesTotal > maxRespSize {
				r.logger.Info("excess data size", slog.Int("bytesTotal", bytesTotal))
				return nil, fmt.Errorf("excess data size")
			}
			checkConeCount = 0

		case <-ctxTimeout.Done():
			return msg.Bytes(), fmt.Errorf("timeout") // 返回超时或取消原因
		case <-checkCone:
			checkConeCount += 1
			if msg.Len() > 0 && checkConeCount > 4 {
				r.logger.Info("timeout", slog.Int("msgLen", msg.Len()))
				return msg.Bytes(), nil
			}
		}
	}

	// not reach here
	// return msg.Bytes(), nil
}

func (r *MongoShell) Stop() {
	r.logger.Info("stop", slog.String("pid", strconv.Itoa(r.Pid)))
	r.StopChan <- struct{}{}
	r.logger.Info("stopped", slog.String("pid", strconv.Itoa(r.Pid)))
}

func precheckInput(ShellBin string, msg []byte) ([]byte, error) {
	// 如果是 mongosh，不需要加 print
	if ShellBin == "mongosh" {
		return msg, nil
	}

	// append "\n" to the end of msg
	if len(msg) == 0 || msg[len(msg)-1] != '\n' {
		msg = append(msg, []byte("\n")...)
	}

	// 避免空的输出
	// reShow, _ := regexp.Compile("(?i)" + `^\s*show\b`)
	reUse, _ := regexp.Compile("(?i)" + `^\s*use\b`)
	reIt, _ := regexp.Compile("(?i)" + `^\s*it\b`)
	if reIt.Match(msg) || reUse.Match(msg) {
		// use xxx
		// it;
		// 一定会有返回，不需要加 print, 其它的可能没有返回
	} else {
		msg = append(msg, []byte("print('')\n")...)
	}

	return msg, nil
}

// SendMsg sends a message to process
func (r *MongoShell) SendMsg(msg []byte) (n int, err error) {
	msg, err = precheckInput(r.ShellBin, msg)
	if err != nil {
		return 0, errors.Wrap(err, "precheckInput")
	}
	n, err = r.ProcessStdin.Write(msg)
	return
}

func isResponseEnd(buf []byte) bool {
	// return len(buf) > 0 && buf[len(buf)-1] == '>' && bytes.Contains(buf, []byte(" [direct: "))
	/*
			{ "_id" : "server_time", "d" : { "openTime" : 1750693149, "dayCounter" : { "count" : 1, "span" : 1, "spanId" : 1486, "offset" : 0 } }, "st" : 1750701216.62 }
		{ "_id" : "match", "d" : { "isSucc" : true, "roleTbl" : {  }, "unionTbl" : {  }, "isEnsure" : false, "hasStart" : false }, "st" : 1750701216.64 }
	*/
	return len(buf) > 0 && buf[len(buf)-1] == '>'
}

// GetGoid extracts the goroutine ID from the runtime stack.
func GetGoid() int64 {
	var buf [64]byte
	n := runtime.Stack(buf[:], false)
	stk := strings.TrimPrefix(string(buf[:n]), "goroutine ")

	// The goroutine ID is typically the first field after "goroutine ".
	idField := strings.Fields(stk)[0]
	id, err := strconv.Atoi(idField)
	if err != nil {
		panic(fmt.Errorf("failed to parse goroutine ID: %v", err))
	}
	return int64(id)
}

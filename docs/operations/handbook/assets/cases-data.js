/* ============================================================
 * MongoDB Handbook · 业务案例数据
 * 来源：IegMongoTeam iWiki 知识库（实战归档）
 * 字段说明：
 *   id        - 案例唯一编号
 *   theme     - 主题分类（bug/perf/topo/backup/migrate/tool/ops）
 *   severity  - 严重级别（P0/P1/P2）
 *   title     - 案例标题
 *   biz       - 业务名（可选）
 *   year      - 时间（可选）
 *   versions  - 受影响版本数组
 *   tags      - 标签数组
 *   summary   - 一句话摘要（卡片正面展示）
 *   iwiki     - iWiki 链接（可选）
 *   detail    - { bg, symptom, cause, fix, takeaway }
 * ============================================================ */

window.HANDBOOK_CASES = [
  /* ===== 1. Bug & 故障类 ===== */
  {
    theme:'bug', severity:'P0',
    title:'4.2.0~4.2.5 KeyNotFound · config 会话缓存爆 100w',
    biz:'job MongoDB 集群', year:'2021-06',
    versions:['4.2.5'],
    tags:['SERVER-42827','KeyNotFound','HMAC','分片集群'],
    summary:'Java driver monitor 线程报 <b>error 211 KeyNotFound</b>，Cache Reader No keys found for HMAC，分片命令失败、chunk 迁移失败、无法访问 config primary。',
    iwiki:'https://iwiki.woa.com/p/924427245',
    detail:{
      bg:'域名 <code>mongos.joblog.bk.db#27000</code>，版本 4.2.5。',
      symptom:`<pre><span class="code-tag">Java driver</span><code>com.mongodb.MongoCommandException: Command failed with error 211 (KeyNotFound):
'Cache Reader No keys found for HMAC that is valid for time: { ts: Timestamp(1624503733, 20) } with id: 0'</code></pre>`,
      cause:'<p>命中 MongoDB 官方 <a href="https://jira.mongodb.org/browse/SERVER-42827" target="_blank" rel="noopener">SERVER-42827</a>：受影响版本 <strong>4.2.0 ~ 4.2.5</strong>。当 config server primary 的 <code>connXXX</code> 达到 <strong>100 万</strong>（默认 <code>maxSessions</code>）即触发。</p>',
      fix:`<ul>
        <li><strong>临时</strong>：config 切主 → 重启 → 再切回，释放连接缓存</li>
        <li><strong>临时 2</strong>：把 <code>maxSessions</code> 调到 100w 之上，延后触发</li>
        <li><strong>长期</strong>：升级到 <strong>4.2.6+</strong>（修复版本）</li>
      </ul>`,
      takeaway:'分片集群部署 4.2.x 时，<strong>禁止</strong>停留在 4.2.5 及更早小版本；同时密切关注 config primary 的会话/连接数。'
    }
  },
  {
    theme:'bug', severity:'P0',
    title:'内核 / Docker urandom 导致 mongos crash',
    versions:['任意'],
    tags:['Docker','urandom','内核','crash'],
    summary:'mongod/mongos 崩溃，日志关键字 <code>cannot open /dev/urandom Operation not permitted</code>，与特定 Docker / 内核版本相关。',
    iwiki:'https://iwiki.woa.com/p/948332906',
    detail:{
      bg:'某些 Docker 版本会定期刷新 <code>/cgroup/devices</code> 信息，导致 <code>/dev/urandom</code> 在该时间点出现异常。',
      symptom:'mongod 或 mongos 进程 crash；日志含 <code>cannot open /dev/urandom Operation not permitted</code>；创建连接时较易触发。',
      cause:'<p>受影响内核（黑名单）：</p><ul><li><code>3.10.107-1-tlinux2-0048</code> ❌</li><li><code>5.4.87-19-0002_plusbeta5</code> ❌</li><li><code>3.10.107-1-tlinux2-0054</code> ✅</li></ul>',
      fix:'<p>避免使用黑名单内的内核版本，或直接使用 <strong>CVM</strong>（非容器）；现网升级到 <code>docker 1.12.10-a43b581+</code>。</p>',
      takeaway:'容器化部署 MongoDB 时，<strong>底层内核 + Docker 版本</strong>本身就是风险面，要纳入兼容矩阵管控。'
    }
  },
  {
    theme:'bug', severity:'P1',
    title:'4.2.x session 不释放',
    versions:['4.2.0','4.2.1','4.2.2','4.2.3','4.2.4','4.2.5'],
    tags:['session 泄漏','LogicalSession'],
    summary:'4.2 系列且 ≤ 4.2.5 的版本存在 session 不释放问题，会逐步耗尽资源。',
    iwiki:'https://iwiki.woa.com/p/948332906',
    detail:{
      bg:'参考社区文章：<a href="https://mongoing.com/archives/73811" target="_blank" rel="noopener">mongoing.com/archives/73811</a>',
      symptom:'连接数持续累积，session 不被回收；最终影响新连接建立。',
      cause:'4.2 早期小版本 session 生命周期管理 bug。',
      fix:'升级至 <strong>4.2.6+</strong>。',
      takeaway:'4.2.x 是高密度 bug 区，所有 4.2.0~4.2.5 集群都应排查升级计划。'
    }
  },
  {
    theme:'bug', severity:'P1',
    title:'mongo-java-driver KeyNotFound · anyAction 角色异常',
    versions:['任意'],
    tags:['Java driver','anyAction','签名','keyId=0'],
    summary:'monitor 线程每 10s 一次 isMaster，偶发 <code>error 211 KeyNotFound</code>。根因是账号配置了 <strong>anyResource + anyAction</strong> 角色。',
    iwiki:'https://iwiki.woa.com/p/948332906',
    detail:{
      bg:'mongo-java-driver 的 monitor thread 周期性执行 <code>isMaster</code>。',
      symptom:`<pre><span class="code-tag">log</span><code>Exception in monitor thread while connecting to server mongos.stress.ccxt.db:27000
error 211 (KeyNotFound): 'Cache Reader No keys found for HMAC...'</code></pre>`,
      cause:'<p><code>system.roles</code> 内存在带 <code>anyResource:true</code> + <code>actions:["anyAction"]</code> 的角色；这导致 <strong>mongos 跳过签名</strong>，返回客户端 <code>keyId=0</code>，引发后续访问异常。</p>',
      fix:`回收带 <code>anyAction</code> 的角色：<pre><span class="code-tag">mongosh</span><code>db.system.roles.find()
db.system.roles.deleteOne({_id:"admin.applyOps"})</code></pre>`,
      takeaway:'避免把 <code>anyResource + anyAction</code> 这种"上帝角色"赋给业务账号。'
    }
  },
  {
    theme:'bug', severity:'P2',
    title:'副本集模式却配置了 shardsvr · TooManyLogicalSessions',
    versions:['≥ 3.6'],
    tags:['副本集','shardsvr','LogicalSessions'],
    summary:'连接数不多却返回 <code>TooManyLogicalSessions</code>，根因是 RS 模式下错误启用了 <code>clusterRole: shardsvr</code>。',
    iwiki:'https://iwiki.woa.com/p/948332906',
    detail:{
      bg:'replicaset 模式部署，但 <code>mongod.conf</code> 配置了 <code>sharding.clusterRole: shardsvr</code>。',
      symptom:'连接数远低于阈值时已收到 <code>TooManyLogicalSessions</code> 错误。',
      cause:'≥ 3.6 版本下，RS 模式不应当声明 <code>shardsvr</code>；该错误配置导致 session 缓存逻辑异常。',
      fix:'<p>从配置文件中删除整个 <code>sharding</code> 段后重启实例。</p>',
      takeaway:'集群类型与 <code>clusterRole</code> 必须严格匹配；配置模板要按集群类型分开维护。'
    }
  },
  {
    theme:'bug', severity:'P2',
    title:'config.system.sessions 未分片 · balancer 关闭过严',
    versions:['任意'],
    tags:['system.sessions','balancer'],
    summary:'<code>config.session</code> 表始终不开启 sharding，间歇性产生热点。',
    iwiki:'https://iwiki.woa.com/p/948332906',
    detail:{
      bg:'参考 <a href="https://jira.mongodb.org/browse/SERVER-46797" target="_blank" rel="noopener">SERVER-46797</a>。',
      symptom:'<code>sh.status()</code> 显示 <code>config.system.sessions</code> 未分片或仅在单 shard。',
      cause:'balancer 长期关闭，导致 system.sessions 集合无法被自动分片初始化。',
      fix:'<p>临时打开 balancer <strong>一段时间</strong>即可让其完成分片初始化；4.4 版本可解决（待确认）。</p>',
      takeaway:'变更窗口前后人为关 balancer 是常态，但要留出一个"开放窗口"让系统集合完成自我分片。'
    }
  },
  {
    theme:'bug', severity:'P2',
    title:'mongodb_exporter 无法采集 hidden 节点',
    versions:['任意'],
    tags:['exporter','监控','hidden'],
    summary:'mongodb_exporter 访问 hidden 节点失败，导致 hidden 节点性能数据缺失。',
    iwiki:'https://iwiki.woa.com/p/948332906',
    detail:{
      bg:'hidden 节点（隐藏成员）通常用于备份与离线分析，但仍需可观测。',
      symptom:'监控面板上 hidden 节点指标全部为 0/无数据。',
      cause:'旧版 percona mongodb_exporter 不识别 hidden 节点。',
      fix:'<p>升级 exporter（2023 年已合并最新 percona mongodb_exporter）。同时区分版本：<code>prome_mongodb_exporter_v42</code>（4.2/4.4/6.0）与 <code>prome_mongodb_exporter</code>（≤ 4.0）。</p>',
      takeaway:'监控组件本身的版本兼容性同样需要随集群版本演进而升级。'
    }
  },

  /* ===== 2. 性能 / 慢查询类 ===== */
  {
    theme:'perf', severity:'P1',
    title:'$or vs $in · cmdb 10s 超时',
    biz:'bk-cloud-cmdb (蓝鲸)', year:'2021-10',
    versions:['4.2.x'],
    tags:['$or','$in','慢查询','索引'],
    summary:'cmdb 查询大量 IP 列表用 <code>$or + $and</code> 拼接，<strong>10 秒超时</strong>；改写为 <code>$in</code> 后耗时降至 <strong>0.03s</strong>。',
    iwiki:'https://iwiki.woa.com/p/1283428328',
    detail:{
      bg:'<code>cc_HostBase</code> 集合，按 1500 个 IP 列表查询，请求体 ~400KB。',
      symptom:`<pre><span class="code-tag">slow log</span><code>command cmdb.cc_HostBase command: find {
  filter: { bk_supplier_account: { $in: [...] },
    $and: [{ $or: [
      { $and:[{bk_host_innerip:"9.79.163.116"}, {bk_cloud_id:0}] },
      { $and:[{bk_host_innerip:"9.68.79.98"},  {bk_cloud_id:0}] },
      ...  // 1500 个 IP
    ]}]}
}  numYields:345  10511ms  ClientDisconnect</code></pre>`,
      cause:'<p>对<strong>同一字段</strong>等值检查使用 <code>$or</code>，等价于发起多次独立查询，无法走单一索引；<code>$or</code> 的条目数 ≈ 1500 时性能崩塌。</p>',
      fix:`<pre><span class="code-tag">优化前 (10s+)</span><code>db.cc_HostBase.find({
  $or:[ {bk_host_innerip:"a"}, {bk_host_innerip:"b"}, ... ]
})</code></pre>
<pre><span class="code-tag">优化后 (0.03s)</span><code>db.cc_HostBase.find({
  bk_host_innerip: { $in: ["a","b",...] },
  bk_supplier_account: { $in: ["0","tencent"] }
})</code></pre>`,
      takeaway:'<strong>同字段等值列表必须用 <code>$in</code></strong>，禁止用 <code>$or</code>；官方文档明确建议（<a href="https://docs.mongodb.com/manual/reference/operator/query/or/" target="_blank" rel="noopener">$or vs $in</a>）。'
    }
  },
  {
    theme:'perf', severity:'P1',
    title:'partialFilterExpression 误用 · 等值查询全表扫描',
    biz:'bk-cloud-cmdb', year:'2023-11',
    versions:['4.2.5'],
    tags:['partialIndex','COLLSCAN','索引未命中'],
    summary:'<code>cc_HostBase</code> 简单等值 <code>find({bk_agent_id:"..."})</code> 走 COLLSCAN 扫 34w 行；根因是 partial index 的过滤条件需要在查询中显式重述。',
    iwiki:'https://iwiki.woa.com/p/4009224534',
    detail:{
      bg:'索引存在 <code>bkcc_unique_bkAgentID</code>，含 <code>partialFilterExpression: { bk_agent_id: { $type: "string", $gt: "" } }</code>。',
      symptom:`<pre><span class="code-tag">slow log</span><code>find { bk_agent_id: "02000000000c42a1ab9f3a169..." }
planSummary: COLLSCAN  docsExamined:345209  1457ms</code></pre>`,
      cause:'<p>partial index 仅为满足 <code>$type:"string"</code> + <code>$gt:""</code> 条件的文档建索引；查询若不<strong>显式包含</strong>这些条件，规划器认为索引可能不完整，<strong>退回全表扫描</strong>。参考 <a href="https://www.mongodb.com/community/forums/t/unique-index-with-partial-filter-is-not-being-used-by-mongodb/120478/3" target="_blank" rel="noopener">官方社区讨论</a>。</p>',
      fix:`<pre><span class="code-tag">改写后走 IXSCAN</span><code>db.cc_HostBase.find({
  bk_agent_id: { $type:"string", $eq:"02000000000c42a1ba2d7a..." }
})</code></pre>
<p>同时建议开发降低相同 <code>bk_agent_id</code> 的请求频率。</p>`,
      takeaway:'设计 partial index 时必须同步公布"查询模板"；DBA 评审上线索引时要把 <code>partialFilterExpression</code> 对应的查询写法写进规范。'
    }
  },
  {
    theme:'perf', severity:'P2',
    title:'压测首查 3 秒 · mongos→shardsvr 连接池冷启动',
    biz:'璀璨星途',
    versions:['≥ 4.4'],
    tags:['warmMinConnections','连接池','冷启动'],
    summary:'压测启动后第一波 DB 查询 ≥ 3s，后续恢复正常；与 mongos→shardsvr 连接池建立有关。',
    iwiki:'https://iwiki.woa.com/p/1283429950',
    detail:{
      bg:'各节点负载均很低，硬件性能不是瓶颈。',
      symptom:'压测首批请求 300ms ~ 3s 慢查询，后续无问题。Redis 路径正常 3-5ms。',
      cause:'mongos 与 shardsvr 之间需要建立连接池，第一次访问时同步等待。',
      fix:'<p>从 4.4 起开启参数：<code>warmMinConnectionsInShardingTaskExecutorPoolOnStartupWaitMS</code>，启动期预热连接池。</p>',
      takeaway:'生产环境上线/扩容后，建议主动 <strong>warm up</strong>，或调大该参数让 mongos 启动期完成池预热。'
    }
  },
  {
    theme:'perf', severity:'P2',
    title:'3.6 计划缓存陈旧 · 查询不走正确索引',
    versions:['3.6'],
    tags:['planCache','索引','explain'],
    summary:'explain 显示走索引，<strong>实际执行</strong>却没有；清空计划缓存后恢复。',
    iwiki:'https://iwiki.woa.com/p/4008458397',
    detail:{
      bg:'某 3.6 集群上同一查询 explain 与实际执行计划不一致。',
      symptom:'explain → IXSCAN ✅；实际执行 → COLLSCAN（监控视角）。',
      cause:'<code>planCache</code> 缓存了旧的次优计划。',
      fix:`<pre><span class="code-tag">mongosh</span><code>db.collection.getPlanCache().listQueryShapes()
db.collection.getPlanCache().clear()</code></pre>`,
      takeaway:'数据分布发生明显变化（大量写入/删除）后，主动 <code>clear()</code> planCache，避免次优计划"卡顿"残留。'
    }
  },
  {
    theme:'perf', severity:'P2',
    title:'klbqpc · 跨日刷新任务 OPS 飙升',
    biz:'klbqpc 卡拉比丘端游',
    versions:['4.2.15'],
    tags:['周期性高峰','分片键','广播查询'],
    summary:'每天早上 6 点跨天玩家任务刷新，<strong>OPS 与 CPU 使用率显著上升</strong>；同时复制集→分片迁移后出现广播查询。',
    detail:{
      bg:'分片集群版本 4.2.15。',
      symptom:'① 每日 06:00 OPS/CPU 高峰；② 部分集合不带分片键导致<strong>广播查询</strong>；③ 小数据量分片集合不带分片键的范围查询耗时 200+ms。',
      cause:'分片键选择不当：未按业务真实查询模式选；小集合分片反而带来路由开销。',
      fix:'<ul><li>对小数据量集合 <strong>取消分片</strong>，改为普通集合 + 范围字段索引，耗时下降明显</li><li>大集合按业务高频查询字段重新选分片键</li></ul>',
      takeaway:'分片不是越多越好；<strong>小集合保持单 shard 反而更快</strong>，分片键必须围绕"高频查询模式"设计。'
    }
  },

  /* ===== 3. 拓扑 / 分片类 ===== */
  {
    theme:'topo', severity:'P1',
    title:'tetris · system.sessions 未分片造成单点',
    biz:'tetris 俄罗斯方块环游记', year:'2021-08',
    versions:['4.2.x'],
    tags:['system.sessions','分片','热点'],
    summary:'分片集群中 <code>config.system.sessions</code> 仅在单 shard，mongos 周期性同步导致单节点 CPU 飙高。',
    iwiki:'https://iwiki.woa.com/p/931103071',
    detail:{
      bg:'分片集群部署后未观察到 system.sessions 分片初始化。',
      symptom:`<pre><span class="code-tag">log</span><code>command config.$cmd update { update: "system.sessions",
  bypassDocumentValidation: false, ordered: false, updates: 1000, ... } 214ms</code></pre>
<p>日志显示 mongos 每 5 分钟把未过期 sessions 同步到 shard 的 system.sessions 表。</p>`,
      cause:'<code>config.system.sessions</code> shard key 仅 <code>{_id:1}</code>，单 chunk 全部落在 <code>tetris-prod-s1</code>，造成单节点压力。',
      fix:`<ul>
        <li><strong>方案 1</strong>：调大 mongos 的 <code>logicalSessionRefreshMillis</code>（默认 300000ms / 5min → 30min）</li>
        <li><strong>方案 2</strong>：对 <code>config.system.sessions</code> 真正做分片初始化（开 balancer 一段时间）</li>
      </ul>`,
      takeaway:'部署完分片集群后，必须验证 <code>config.system.sessions</code> 已被均匀分布。'
    }
  },
  {
    theme:'topo', severity:'P1',
    title:'2.4 · collection 过多导致复制异常',
    versions:['2.4'],
    tags:['nssize','复制','STARTUP2'],
    summary:'backup 节点不断 resync，状态卡在 STARTUP2；日志报 <code>too many namespaces/collections</code>。',
    iwiki:'https://iwiki.woa.com/p/4014259309',
    detail:{
      bg:'2.4 老版本 MMAPv1 引擎下，namespace 数量受 <code>nssize</code> 限制。',
      symptom:`<pre><span class="code-tag">mongo.log</span><code>[rsSync] error building index: 10081 too many namespaces/collections
[rsSync] ERROR: error: exception cloning object in dynamic.system.indexes
   too many namespaces/collections
replSet initial sync exception: 10081 too many namespaces/collections</code></pre>`,
      cause:'<code>mongo.conf</code> 中 <code>nssize=16</code> 已无法容纳全部 namespace。',
      fix:'<p>调整 <code>nssize=32</code>（<strong>注意单位为 MB</strong>），重启实例后同步恢复。</p>',
      takeaway:'2.4 是 EOL 版本；新部署绝对不要用，存量集群务必规划迁移。'
    }
  },
  {
    theme:'topo', severity:'P2',
    title:'mongodump 域名连接报 CursorNotFound',
    versions:['4.2','100.7.1'],
    tags:['mongodump','CLB','会话保持'],
    summary:'通过<strong>域名 / VIP</strong> 连 mongos 跑 mongodump 报 <code>CursorNotFound</code>；直连 mongos IP 不报错。',
    iwiki:'https://iwiki.woa.com/p/4008173577',
    detail:{
      bg:'4.2 分片集群，mongodump 4.2 / 100.7.1 均复现。',
      symptom:`<pre><span class="code-tag">err</span><code>Failed: error writing data for collection \`2.ds_info_13\` to disk:
error reading collection: (CursorNotFound) Cursor not found
(namespace: \'2.ds_info_13\', id: 5838431923177422211).</code></pre>`,
      cause:'mongodump 会发起 <strong>2 个连接</strong>，两个连接落在不同 mongos 时 cursor 失效。',
      fix:'<ul><li>方案 1：腾讯云 CLB 启用 <strong>会话保持</strong>（同源 IP → 同 mongos）</li><li>方案 2：直接连 mongos 物理 IP</li></ul>',
      takeaway:'分片集群 + LB 部署形态下，所有<strong>多连接客户端</strong>（mongodump、mongorestore、自定义脚本）都要确认 LB 的会话保持设置。'
    }
  },
  {
    theme:'topo', severity:'P2',
    title:'configsvr + mongos 整体替换流程',
    versions:['任意'],
    tags:['configsvr','mongos','替换'],
    summary:'分片集群中 configsvr 与 mongos 的"无中断"替换 5 步法。',
    iwiki:'https://iwiki.woa.com/p/4006818693',
    detail:{
      bg:'机器搬迁、机型升级、机房迁移等场景。',
      symptom:'需要替换 configsvr 与 mongos 而保持业务无感知。',
      cause:'configsvr 是分片元数据核心；替换不当会导致路由错乱。',
      fix:`<ol>
        <li>新的 configsvr 上架，并替换其中 2 个节点</li>
        <li>修改配置项指向<strong>新的 3 个节点</strong></li>
        <li>上架新 mongos 并激活；此时新旧 mongos 都正常服务</li>
        <li>下架旧 mongos</li>
        <li>最后一个 configsvr <code>stepDown</code> 并替换</li>
      </ol>`,
      takeaway:'configsvr 替换的核心是"先扩后缩 + stepDown"，<strong>永远不能同时替换 majority 节点</strong>。'
    }
  },

  /* ===== 4. 备份 / 回档类 ===== */
  {
    theme:'backup', severity:'P1',
    title:'4.2 分片集群 Restore 完整流程',
    versions:['4.2'],
    tags:['mongodump','mongorestore','clusterId'],
    summary:'官方未提供基于 mongodump/mongorestore 的分片集群备份方案；本案例摸索出 <strong>standalone → 维护元数据 → 启动</strong> 的完整路径。',
    iwiki:'https://iwiki.woa.com/p/4010429492',
    detail:{
      bg:'相比副本集 restore，分片集群多出 <strong>configsvr ↔ shardsvr 元数据维护</strong> 这一关键步骤。',
      symptom:'三处元数据必须保持一致：<ul><li><code>configsvr.config.shard.host</code> = shardsvr 连接串</li><li><code>configsvr.config.version.clusterId</code> = shardsvr <code>shardIdentity.clusterId</code></li><li><code>shardsvr.shardIdentity.configsvrConnectionString</code> = configsvr 连接串</li></ul>',
      cause:'分片集群元数据强耦合 configsvr 与 shardsvr。',
      fix:`<p><strong>configsvr 处理：</strong></p>
<ol>
  <li>注释 <code>sharding</code>/<code>replication</code> 段，以 standalone 启动</li>
  <li>用 GCS 单进程回档功能 restore 数据</li>
  <li><code>config.shards</code> 更新 host 字段为新 shardsvr 连接串</li>
  <li>关掉 balancer：<code>db.settings.insert({_id:"balancer",mode:"full",stopped:true})</code></li>
  <li>恢复配置以 <code>clusterRole: configsvr</code> 启动</li>
  <li>记录新的 <code>clusterId</code></li>
</ol>
<p><strong>shardsvr 处理：</strong></p>
<ol>
  <li>同样以 standalone 启动</li>
  <li>restore 数据</li>
  <li>insert <code>shardIdentity</code> 到 <code>admin.system.version</code>（4.2 不允许 update，必须 insert）</li>
  <li>恢复 <code>clusterRole: shardsvr</code> 启动</li>
</ol>
<p>最后启动 mongos 即可。</p>`,
      takeaway:'分片集群备份方案必须配套<strong>元数据脚本</strong>，否则 restore 出来的集群路由错乱。参考 <a href="https://www.mongodb.com/docs/v4.4/tutorial/restore-sharded-cluster/" target="_blank" rel="noopener">官方文档</a>。'
    }
  },

  /* ===== 5. 迁移 / 扩缩容类 ===== */
  {
    theme:'migrate', severity:'P1',
    title:'xssh · 5 区分服 mongos/shard 缩容',
    biz:'xssh 小森生活', year:'2022-07',
    versions:['任意'],
    tags:['缩容','机型变更','分服'],
    summary:'5 个分服（iosqq/ioswx/androidqq/androidwx/游客服），mongos 从 16 个 D12-30-100-10 缩到 6 个 D4-15-100-10；shard 从 D7-29-300-10-Z 缩到 D4-20-100-10-Z。',
    iwiki:'https://iwiki.woa.com/p/931103786',
    detail:{
      bg:'游戏运营进入稳定期，资源利用率下降，需要降本。',
      symptom:'容量充裕但成本高；机型规格远超实际需求。',
      cause:'初期按峰值容量预估，后期没有及时降配。',
      fix:'<ol><li>shard：D7-29-300-10-Z → D4-20-100-10-Z</li><li>mongos 实例数：16 → 6，机型 D12-30-100-10 → D4-15-100-10</li><li>分阶段缩容（先验证 1 个区，再推广）</li></ol>',
      takeaway:'游戏类业务有明显的"上线 → 衰减"曲线，缩容也是常态运维；务必<strong>分批 + 灰度</strong>。'
    }
  },
  {
    theme:'migrate', severity:'P1',
    title:'vega · 街霸合服 30→10 节点',
    biz:'vega 街霸', year:'2021-07',
    versions:['任意'],
    tags:['合服','mongodump','mongorestore'],
    summary:'将 sq 后 30 个分服合并到前 10 个分服：S11~S40 → S01~S10，按 4 节点一组合并。',
    iwiki:'https://iwiki.woa.com/p/863430064',
    detail:{
      bg:'街霸合服需求，4 个分服合并为 1 个。',
      symptom:'30 个分服合到 10 个分服，需要保留数据完整性。',
      cause:'游戏中后期减少运维成本与玩家分散度的常规操作。',
      fix:'<ol><li><code>mongodump</code> 各源服数据</li><li>删除 <code>admin</code>/<code>test</code>/<code>config</code> 数据库（避免冲突）</li><li><code>mongorestore</code> 到目标分服</li><li>分批回收资源（QQ 区先，WX 区观察后再回收）</li></ol>',
      takeaway:'合服流程必须"先验证、再回收"；保留观察期至少 2~3 天再下架资源。'
    }
  },
  {
    theme:'migrate', severity:'P2',
    title:'基于实例迁移的扩容缩容（GCS 单据流）',
    versions:['任意'],
    tags:['扩容','缩容','GCS 单据'],
    summary:'通过 <strong>新增 SECONDARY → 域名切换 → 下架旧实例</strong> 的单据序列完成扩缩容。',
    iwiki:'https://iwiki.woa.com/p/284630719',
    detail:{
      bg:'单机器实例数增多导致内存压力 / 想合并机器降本时使用。',
      symptom:'需要在不中断服务的前提下迁移实例。',
      cause:'单纯关停-迁移会有中断；副本集机制可平滑过渡。',
      fix:`<p><strong>扩容顺序：</strong></p>
<ol>
  <li>准备新机器，安装 shardsvr-tmp（AreaId/SetId 与原实例相同；副本集模式端口也要相同）</li>
  <li>用"增加节点"单据加入 RS（业务高峰建议 <code>priority:0</code>）</li>
  <li>等同步完成 → SECONDARY</li>
  <li>执行"域名切换"</li>
  <li>调高新实例 CacheSize</li>
  <li>下架旧实例</li>
</ol>
<p><strong>缩容</strong>：步骤相同；要注意现有实例内存使用量，必要时先调小 CacheSize。</p>`,
      takeaway:'同步失败（卡 RECOVERING）时改用 <strong>fsyncLock + 拷贝数据文件</strong> 的 <code>resync-replica-set-member</code> 流程；3.0 WiredTiger 不支持此法。'
    }
  },

  /* ===== 6. 工具集 ===== */
  {
    theme:'tool', severity:'P2',
    title:'MongoDB 慢查询分析工具（基于 ES + Grafana）',
    versions:['任意'],
    tags:['慢查询','Grafana','火焰图','ES'],
    summary:'从 ES 拉慢查询日志，写入 spider 集群，通过 Grafana 提供曲线/饼图/火焰图/表格多视图，支持 <strong>业务→集群→实例</strong> 三级下钻分析。',
    iwiki:'https://iwiki.woa.com/p/278981241',
    detail:{
      bg:'传统 mongo profiling 对性能影响大；需要"零侵入"的慢查询分析方案。',
      symptom:'人工抓 explain 与 profile 效率低，无法横向对比业务。',
      cause:'缺少统一的诊断平台。',
      fix:`<ul>
        <li>不开 profiling，<strong>性能影响为零</strong></li>
        <li>正则矩阵抓取多版本不同操作类型的慢查询日志</li>
        <li>实参 → 形参替换 + 哈希作为主键聚合统计</li>
        <li>top5 自动连接实际数据库执行 explain plan</li>
        <li>规则表检查：<code>totalDocsExamined ≫ totalKeysExamined</code> 或 <code>COLLSCAN</code> → 自动生成"缺失索引"建议</li>
      </ul>
      <p>入口：<a href="http://monitor.gcs.ied.com/d/xtGpK8qZk/mongodb-man-cha-xun-fen-xi" target="_blank" rel="noopener">Grafana MongoDB 慢查询分析</a></p>`,
      takeaway:'慢查询治理需要平台级工具；引入"自动给优化建议"能极大降低 DBA 重复劳动。'
    }
  },

  /* ===== 7. 单据指引 ===== */
  {
    theme:'ops', severity:'P2',
    title:'GCS 单据指引 · 安装 MongoDB',
    versions:['任意'],
    tags:['GCS 单据','安装','部署'],
    summary:'副本集 / 分片集群两种安装路径；不同副本集端口错开便于后续合并；单机多实例 WTCacheSize 总和 ≤ 内存 60%。',
    iwiki:'https://iwiki.woa.com/p/284630719',
    detail:{
      bg:'业务新上线场景。',
      symptom:'需要标准化的部署流程。',
      cause:'手工部署易出错且难审计。',
      fix:`<p><strong>副本集</strong>：</p>
<ol>
  <li>"MongoDB-安装"单据，类型选"副本集"</li>
  <li>不同副本集端口错开</li>
  <li>WTCacheSize 总和 ≤ 内存 60%</li>
  <li>Backup 节点规格可为 Primary/Secondary 的一半</li>
  <li>执行"部署监控"单据</li>
</ol>
<p><strong>分片集群</strong>：</p>
<ol>
  <li>安装 configsvr 副本集（≥ 3.0 setid 固定为 <code>conf</code> 自动注册 configdb；2.4 需手动配 <code>$app→MongoDB→cluster→$ClusterID→$configdb</code>）</li>
  <li>安装各分片副本集</li>
  <li>安装 mongos</li>
  <li>连 mongos 执行 <code>sh.addShard</code> 加分片</li>
  <li>关闭 balancer + 设 chunkSize（默认 64M，最大 1024M）：<br><code>sh.setBalancerState(false)</code><br><code>db.getSisterDB('config').settings.save({_id:'chunksize', value:512})</code></li>
  <li>执行"激活 Mongos 域名"+"部署监控"</li>
  <li>建库表：<code>sh.enableSharding</code> + <code>sh.shardCollection</code></li>
</ol>`,
      takeaway:'端口规划是隐藏的运维财富：错开端口后，将来"机器合并"时不需要改任何业务连接串。'
    }
  },
  {
    theme:'ops', severity:'P0',
    title:'GCS 单据指引 · 部分/全量回档',
    versions:['任意'],
    tags:['回档','构造数据','recover'],
    summary:'区分<strong>部分数据回档</strong>（受影响玩家可枚举）与<strong>全量数据回档</strong>（影响全服）两种方案。',
    iwiki:'https://iwiki.woa.com/p/284630719',
    detail:{
      bg:'业务出现复制 bug 或误操作，需要回退到过去时间点。',
      symptom:'数据状态错误，需要恢复。',
      cause:'人为误操作 / 业务 bug / 程序逻辑缺陷。',
      fix:`<p><strong>部分数据回档</strong>（推荐）：</p>
<ol>
  <li>申请新机器</li>
  <li>"MongoDB-安装"部署 shardsvr-primary（单点）</li>
  <li>"MongoDB-addUser" 增加 recover 用户（需 AnyAction 权限）</li>
  <li>"MongoDB-构造数据"</li>
  <li>请产品给出受影响 QQ/openid 列表 → 封号 → 开服</li>
  <li>对受影响用户做数据替换（脚本编写或开发协助）</li>
  <li>验证后解封</li>
</ol>
<p><strong>全量数据回档</strong>：</p>
<ol>
  <li>同样准备新机器 + 部署 shardsvr-primary</li>
  <li>构造数据完成后导出，再导入现网 DB（停服状态下操作）</li>
</ol>`,
      takeaway:'<strong>部分回档优先</strong>，全量回档压力大；任何回档前必须先备份。'
    }
  },
  {
    theme:'ops', severity:'P1',
    title:'故障替换流程',
    versions:['任意'],
    tags:['故障替换','RECOVERING','fsyncLock'],
    summary:'机器故障时通过 so.ied.com 申请新机 → 部署 tmp 节点 → 故障替换单据 → 部署监控 → 下架旧节点。',
    iwiki:'https://iwiki.woa.com/p/284630719',
    detail:{
      bg:'某机器突发故障。',
      symptom:'实例不可用，需要紧急替换。',
      cause:'硬件故障 / 系统异常 / 网络隔离等。',
      fix:`<ol>
        <li>so.ied.com 用"故障替换"申请同机房同规格新机</li>
        <li>"MongoDB-安装"部署相应数量的 shardsvr-tmp</li>
        <li>"MongoDB-故障替换"单据完成实例替换</li>
        <li>"MongoDB-部署监控"</li>
        <li>"MongoDB-下架"旧实例</li>
      </ol>
      <p>同步失败（RECOVERING）时改用 <strong>fsyncLock + 拷贝数据文件</strong>：</p>
      <pre><span class="code-tag">mongosh</span><code>// 在健康的 SECONDARY B 上
db.fsyncLock()
// 拷贝 B 数据文件到故障节点 C 的对应目录
// 启动 C
db.fsyncUnlock()  // 在 B 上执行</code></pre>`,
      takeaway:'<strong>WiredTiger 3.0 不能用 fsyncLock 拷文件法</strong>；超大文件传输考虑 tsunami 加速。'
    }
  }
];

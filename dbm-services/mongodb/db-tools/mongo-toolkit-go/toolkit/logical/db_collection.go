/*
 * @Author: cycker cycker@gmail.com
 * @Date: 2025-07-07 15:33:09
 * @LastEditors: cycker cycker@gmail.com
 * @LastEditTime: 2025-07-08 10:23:52
 * @FilePath: /dbm-services/mongodb/db-tools/mongo-toolkit-go/toolkit/logical/db_collection.go
 * @Description: 这是默认设置,请设置`customMade`, 打开koroFileHeader查看配置 进行设置: https://github.com/OBKoro1/koro1FileHeader/wiki/%E9%85%8D%E7%BD%AE
 */
package logical

import (
	"context"
	"dbm-services/mongodb/db-tools/mongo-toolkit-go/pkg/mymongo"
	"time"

	"github.com/pkg/errors"
	"go.mongodb.org/mongo-driver/bson"
)

// DbCollection dbName和collectionList和不匹配的collectionList的结构体
type DbCollection struct {
	Db         string
	Col        []string
	notMachCol []string
}

var ErrorNoMatchDb error = errors.New("NoMatchDb")

// GetDbCollectionWithFilter 获取指定mongo的所有db和collection
func GetDbCollectionWithFilter(ip, port, user, pass, authDb string, filter *NsFilter) ([]DbCollection, error) {
	client, err := mymongo.Connect(ip, port, user, pass, authDb, 60*time.Second)
	if err != nil {
		return nil, errors.Wrap(err, "Connect")
	}
	ctx, cancel := context.WithTimeout(context.Background(), 60*time.Second)
	dbList, err := client.ListDatabaseNames(ctx, bson.M{})
	if err != nil {
		cancel()
		return nil, errors.Wrap(err, "ListDatabaseNames")
	}
	cancel()

	var dbColList []DbCollection
	for _, dbName := range dbList {
		ctx, cancel := context.WithTimeout(context.Background(), 60*time.Second)
		colList, err := client.Database(dbName).ListCollectionNames(ctx, bson.M{})
		if err != nil {
			cancel()
			return nil, errors.Wrap(err, "ListCollectionNames")
		}
		cancel()
		matched, notMatched := filter.FilterTbV2(dbName, colList)
		dbColList = append(dbColList, DbCollection{
			Db:         dbName,
			Col:        matched,
			notMachCol: notMatched,
		})
	}
	return dbColList, nil
}

// GetDbCollection 获取指定mongo的所有db和collection
func GetDbCollection(ip, port, user, pass, authDb string, excludeSysDb bool) ([]DbCollection, error) {
	client, err := mymongo.Connect(ip, port, user, pass, authDb, 60*time.Second)
	if err != nil {
		return nil, errors.Wrap(err, "Connect")
	}
	defer client.Disconnect(context.Background())
	ctx, cancel := context.WithTimeout(context.Background(), 60*time.Second)
	dbList, err := client.ListDatabaseNames(ctx, bson.M{})
	if err != nil {
		cancel()
		return nil, errors.Wrap(err, "ListDatabaseNames")
	}
	cancel()
	var dbColList []DbCollection
	for _, dbName := range dbList {
		if excludeSysDb && mymongo.IsSysDb(dbName) {
			continue
		}
		ctx2, cancel2 := context.WithTimeout(context.Background(), 120*time.Second)
		colList, err := client.Database(dbName).ListCollectionNames(ctx2, bson.M{})
		if err != nil {
			cancel2()
			return nil, errors.Wrap(err, "ListCollectionNames")
		}
		cancel2()

		var dbCol DbCollection
		dbCol.Db = dbName
		dbCol.Col = colList
		dbCol.notMachCol = nil
		dbColList = append(dbColList, dbCol)
	}
	return dbColList, nil
}

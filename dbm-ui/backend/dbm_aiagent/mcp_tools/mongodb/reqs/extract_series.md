_extract_series_stats

1. 每个series的 
min: min value
max: max value
avg: avg value
peak_time: the time of max value
null_count: null value count

2. 增加total series, 值为所有serices的和

先生成xcode


_extract_series_stats 如果datapoint总数超过n个,n默认为6400，则将datapoint的值设置提醒字段，大意为数据量过大，请缩小时间范围以减少数据量


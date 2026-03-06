import math
import uuid
import random
import os
from utils.auxiliary_util import haversine_distance, log_output, TRACK_POINT_DECIMAL_PLACES, get_current_epoch_ms, SportsUploaderError


def read_route_from_file(file_path):
    """从文件读取路线坐标，每行格式：经度,纬度"""
    coords = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split(',')
            if len(parts) != 2:
                continue
            try:
                lon, lat = float(parts[0]), float(parts[1])
                coords.append((lon, lat))
            except ValueError:
                continue
    if not coords:
        raise SportsUploaderError(f"路线文件为空或格式不正确: {file_path}")
    return coords


def densify_route(coords, interval_m):
    """在相邻坐标点之间按距离间隔插入中间点，增加轨迹密度"""
    if len(coords) < 2:
        return list(coords)

    result = [coords[0]]
    for i in range(len(coords) - 1):
        lon1, lat1 = coords[i]
        lon2, lat2 = coords[i + 1]
        seg_dist = haversine_distance(lat1, lon1, lat2, lon2)

        if seg_dist <= 0 or interval_m <= 0:
            result.append(coords[i + 1])
            continue

        n = int(seg_dist / interval_m)
        for j in range(1, n + 1):
            frac = j / (n + 1)
            mid_lon = lon1 + frac * (lon2 - lon1)
            mid_lat = lat1 + frac * (lat2 - lat1)
            result.append((mid_lon, mid_lat))

        result.append(coords[i + 1])
    return result


def route_total_distance(coords):
    """计算路线总长度（米）"""
    dist = 0
    for i in range(len(coords) - 1):
        lon1, lat1 = coords[i]
        lon2, lat2 = coords[i + 1]
        dist += haversine_distance(lat1, lon1, lat2, lon2)
    return dist


def _take_partial(coords, distance_m):
    """沿路线取指定距离的部分坐标"""
    if len(coords) < 2:
        return list(coords)

    result = [coords[0]]
    traveled = 0

    for i in range(len(coords) - 1):
        lon1, lat1 = coords[i]
        lon2, lat2 = coords[i + 1]
        seg = haversine_distance(lat1, lon1, lat2, lon2)

        if traveled + seg <= distance_m:
            result.append(coords[i + 1])
            traveled += seg
        else:
            leftover = distance_m - traveled
            if seg > 0:
                frac = leftover / seg
                final_lon = lon1 + frac * (lon2 - lon1)
                final_lat = lat1 + frac * (lat2 - lat1)
                result.append((final_lon, final_lat))
            break

    return result


def build_path_for_distance(coords, target_m, log_cb=None):
    """循环路线坐标直到达到目标距离"""
    loop_dist = route_total_distance(coords)
    if loop_dist <= 0:
        return list(coords)

    # 起终点距离 ≤ 20m 视为闭合环路
    s_lon, s_lat = coords[0]
    e_lon, e_lat = coords[-1]
    gap = haversine_distance(s_lat, s_lon, e_lat, e_lon)
    is_loop = gap <= 20

    result = []
    accumulated = 0

    if is_loop:
        full_loops = int(target_m / loop_dist)
        for _ in range(full_loops):
            result.extend(coords)
            accumulated += loop_dist

        remaining = target_m - accumulated
        if remaining > 0:
            result.extend(_take_partial(coords, remaining))
    else:
        # 非闭合路线使用往返模式
        forward = coords
        backward = coords[::-1]
        round_trip = loop_dist * 2

        full_trips = int(target_m / round_trip)
        for _ in range(full_trips):
            result.extend(forward)
            result.extend(backward)
            accumulated += round_trip

        remaining = target_m - accumulated
        if remaining > 0:
            if remaining <= loop_dist:
                result.extend(_take_partial(forward, remaining))
            else:
                result.extend(forward)
                remaining -= loop_dist
                result.extend(_take_partial(backward, remaining))

    actual = route_total_distance(result)
    log_output(f"路线: 单圈{loop_dist:.0f}m, 生成{actual:.0f}m (目标{target_m:.0f}m)", "info", log_cb)
    return result


def split_track_into_segments(all_points_with_time, total_duration_sec, min_segment_points=5, stop_check_cb=None):
    """将轨迹点拆分为多个轨迹段"""
    tracks = []

    status_map = {
        "normal": "0",
        "stop": "0",
        "invalid": "2",
    }

    current_start_point_idx = 0

    if not all_points_with_time:
        return tracks

    while current_start_point_idx < len(all_points_with_time):
        if stop_check_cb and stop_check_cb():
            log_output("轨迹生成被中断。", "warning")
            raise SportsUploaderError("任务已停止。")

        segment_points = []

        remaining_points = len(all_points_with_time) - current_start_point_idx
        if remaining_points <= min_segment_points:
            segment_length = remaining_points
        else:
            segment_length = random.randint(min_segment_points, max(min_segment_points, remaining_points // 3))
            if segment_length == 1 and remaining_points > 1:
                segment_length = min_segment_points

        segment_points = all_points_with_time[current_start_point_idx: current_start_point_idx + segment_length]
        current_start_point_idx += segment_length

        if not segment_points:
            continue

        rand_val = random.random()
        if rand_val < 0.8:
            segment_status = "normal"
        elif rand_val < 0.9:
            segment_status = "invalid"
        else:
            segment_status = "stop"

        segment_tstate = status_map.get(segment_status, "0")

        segment_distance = 0
        if len(segment_points) > 1:
            for i in range(len(segment_points) - 1):
                p1 = segment_points[i]['latLng']
                p2 = segment_points[i + 1]['latLng']
                segment_distance += haversine_distance(p1['latitude'], p1['longitude'], p2['latitude'], p2['longitude'])

        segment_start_time_ms = segment_points[0]['locatetime']
        segment_end_time_ms = segment_points[-1]['locatetime']
        segment_duration_sec = math.ceil((segment_end_time_ms - segment_start_time_ms) / 1000)

        tracks.append({
            "counts": len(segment_points),
            "distance": segment_distance,
            "duration": segment_duration_sec,
            "points": segment_points,
            "status": segment_status,
            "trid": str(uuid.uuid4()),
            "tstate": segment_tstate,
            "stime": segment_start_time_ms // 1000,
            "etime": segment_end_time_ms // 1000
        })

    return tracks


def generate_running_data_payload(config, required_signpoints, point_rules_data, log_cb=None, stop_check_cb=None):
    """生成跑步数据"""
    from utils.auxiliary_util import get_base_path

    # 读取路线文件
    base_path = get_base_path()
    route_file = os.path.join(base_path, 'default.txt')
    raw_coords = read_route_from_file(route_file)

    # 百度坐标偏移校正（百度坐标 → GCJ-02）
    lon_offset = -0.00651271494735 + 0.000094
    lat_offset = -0.00560888976477 - 0.000700
    coords = [(lon + lon_offset, lat + lat_offset) for lon, lat in raw_coords]
    log_output(f"已加载路线，共 {len(coords)} 个坐标点", "info", log_cb)

    # 配速参数：5min/km
    target_km = config.get('RUN_DISTANCE_KM', 5)
    target_m = target_km * 1000
    pace_sec_per_km = 5 * 60  # 5分钟/公里 = 300秒/公里
    total_sec = int(pace_sec_per_km * target_km)
    interval = int(config.get('INTERVAL_SECONDS', 3))
    if interval <= 0:
        interval = 3
    speed_mps = target_m / total_sec  # ~3.33 m/s

    # 加密路线点并循环至目标距离
    step_dist = speed_mps * interval
    dense_coords = densify_route(coords, step_dist)
    path_coords = build_path_for_distance(dense_coords, target_m, log_cb)

    # 更新起点坐标（用于 point-rule API 调用）
    if path_coords:
        config['START_LONGITUDE'] = path_coords[0][0]
        config['START_LATITUDE'] = path_coords[0][1]

    # 生成带时间戳的轨迹点
    base_time_ms = config.get('START_TIME_EPOCH_MS') or get_current_epoch_ms()
    points = []
    cum_dist = 0

    for i, (lon, lat) in enumerate(path_coords):
        if stop_check_cb and stop_check_cb():
            raise SportsUploaderError("任务已停止。")

        if i > 0:
            prev_lon, prev_lat = path_coords[i - 1]
            cum_dist += haversine_distance(prev_lat, prev_lon, lat, lon)

        t_ms = base_time_ms + int(cum_dist / speed_mps * 1000) if speed_mps > 0 else base_time_ms

        fmt_lat = f"{lat:.{TRACK_POINT_DECIMAL_PLACES}f}"
        fmt_lon = f"{lon:.{TRACK_POINT_DECIMAL_PLACES}f}"

        points.append({
            "latLng": {"latitude": float(fmt_lat), "longitude": float(fmt_lon)},
            "location": f"{fmt_lon},{fmt_lat}",
            "step": 0,
            "locatetime": t_ms
        })

    # 统计实际距离和时长
    actual_dist = cum_dist
    actual_sec = 0
    if points:
        actual_sec = max(1, (points[-1]['locatetime'] - points[0]['locatetime']) // 1000)

    tracks_list = split_track_into_segments(points, actual_sec, stop_check_cb=stop_check_cb)

    # 配速计算
    run_id = point_rules_data.get('rules', {}).get('id', 9)
    sp_avg = round(actual_sec / (actual_dist / 1000) / 60) if actual_dist > 0 else 5

    rules_meta = point_rules_data.get('rules', {})
    sp_min = rules_meta.get('spmin', 180)
    sp_max = rules_meta.get('spmax', 540)
    sp_avg_s = sp_avg * 60

    if actual_dist > 0:
        if sp_avg_s < sp_min:
            log_output(f"配速 {sp_avg}min/km 过快，调整为 {math.ceil(sp_min / 60)}min/km", "warning", log_cb)
            sp_avg = math.ceil(sp_min / 60)
        elif sp_avg_s > sp_max:
            log_output(f"配速 {sp_avg}min/km 过慢，调整为 {math.floor(sp_max / 60)}min/km", "warning", log_cb)
            sp_avg = math.floor(sp_max / 60)

    request_body = [
        {
            "fravg": 0,
            "id": run_id,
            "sid": str(uuid.uuid4()),
            "signpoints": [],
            "spavg": sp_avg,
            "state": "0",
            "tracks": tracks_list,
            "userId": config['USER_ID']
        }
    ]
    return request_body, actual_dist, actual_sec
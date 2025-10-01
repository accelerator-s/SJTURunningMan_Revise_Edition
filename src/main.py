import time
import datetime
from src.api_client import get_authorization_token_and_rules, upload_running_data
from src.data_generator import generate_running_data_payload
from src.utils import log_output, SportsUploaderError, get_current_epoch_ms

def run_sports_upload(config, progress_callback=None, log_cb=None, stop_check_cb=None):
    """
    核心的跑步数据生成和上传逻辑，接收配置字典和进度回调函数。
    progress_callback: 接收 (current_value, max_value, message)
    log_cb: 接收 (message, level)
    stop_check_cb: 一个函数，调用时返回True表示请求停止
    """
    log_output("--- Starting Sports Upload Process ---", callback=log_cb)

    if stop_check_cb and stop_check_cb():
        log_output("任务被请求停止，正在退出...", "warning", log_cb)
        return False, "任务已停止。"

    auth_token_for_upload = None
    required_signpoints = []
    point_rules_data = {}

    try:
        log_output("Step 1/3: Getting Authorization Token and Point Rules...", callback=log_cb)
        if progress_callback: progress_callback(10, 100, "获取认证信息和跑步规则...")

        if stop_check_cb and stop_check_cb():
            log_output("任务被请求停止，正在退出...", "warning", log_cb)
            return False, "任务已停止。"

        auth_token_for_upload, point_rules_data = get_authorization_token_and_rules(config, log_cb=log_cb, stop_check_cb=stop_check_cb)
        required_signpoints = [p for p in point_rules_data.get('points', []) if p.get('isneed') == 'Y']
        log_output(f"Required Signpoints for rule: {required_signpoints}", callback=log_cb)

        rules_meta = point_rules_data.get('rules', {})
        if rules_meta:
            min_sp_s_per_km = rules_meta.get('spmin', 180)
            max_sp_s_per_km = rules_meta.get('spmax', 540)

            if min_sp_s_per_km and max_sp_s_per_km:
                min_speed_mps = 1000 / max_sp_s_per_km if max_sp_s_per_km > 0 else 0
                max_speed_mps = 1000 / min_sp_s_per_km if min_sp_s_per_km > 0 else 0

                if config["RUNNING_SPEED_MPS"] < min_speed_mps:
                    log_output(
                        f"Adjusting running speed from {config['RUNNING_SPEED_MPS']:.2f} m/s to minimum allowed {min_speed_mps:.2f} m/s",
                        "warning", log_cb)
                    config["RUNNING_SPEED_MPS"] = min_speed_mps
                elif config["RUNNING_SPEED_MPS"] > max_speed_mps:
                    log_output(
                        f"Adjusting running speed from {config['RUNNING_SPEED_MPS']:.2f} m/s to maximum allowed {max_speed_mps:.2f} m/s",
                        "warning", log_cb)
                    config["RUNNING_SPEED_MPS"] = max_speed_mps

                log_output(
                    f"Pace rule: {min_sp_s_per_km / 60:.0f}'-{max_sp_s_per_km / 60:.0f}' min/km. Using adjusted speed: {config['RUNNING_SPEED_MPS']:.2f} m/s",
                    callback=log_cb)
        else:
            log_output("Warning: Could not retrieve pace rules from point-rule response. Using default speed.",
                       "warning", log_cb)

    except SportsUploaderError as e:
        log_output(f"Fatal: Failed during authentication or rule retrieval: {e}", "error", log_cb)
        return False, str(e)
    except Exception as e:
        log_output(f"An unexpected error occurred during auth/rules retrieval: {e}", "error", log_cb)
        return False, str(e)

    if stop_check_cb and stop_check_cb():
        log_output("任务被请求停止，正在退出...", "warning", log_cb)
        return False, "任务已停止。"

    log_output("\nStep 2/3: Generating Running Data...", callback=log_cb)
    if progress_callback: progress_callback(40, 100, "生成跑步数据...")
    running_data_payload = None
    total_dist = 0
    total_dur = 0
    try:
        running_data_payload, total_dist, total_dur = generate_running_data_payload(
            config,
            required_signpoints,
            point_rules_data,
            log_cb=log_cb,
            stop_check_cb=stop_check_cb
        )

        log_output(f"Generated {len(running_data_payload[0]['tracks'])} track segments.", callback=log_cb)
        log_output(f"Total simulated distance: {total_dist:.2f} meters", callback=log_cb)
        log_output(f"Total simulated duration: {total_dur} seconds", callback=log_cb)
        log_output(f"Simulated average pace: {running_data_payload[0]['spavg']} min/km", callback=log_cb)

        if running_data_payload and running_data_payload[0]['tracks']:
            first_point_locatetime_ms = running_data_payload[0]['tracks'][0]['points'][0]['locatetime']
            first_point_datetime = datetime.datetime.fromtimestamp(first_point_locatetime_ms / 1000).strftime('%Y-%m-%d %H:%M:%S')
            log_output(
                f"Actual start time of run (from first point): {first_point_datetime} (Epoch MS: {first_point_locatetime_ms})",
                callback=log_cb)

    except SportsUploaderError as e:
        log_output(f"Failed to generate running data: {e}", "error", log_cb)
        return False, str(e)
    except Exception as e:
        log_output(f"An unexpected error occurred during data generation: {e}", "error", log_cb)
        return False, str(e)

    if stop_check_cb and stop_check_cb():
        log_output("任务被请求停止，正在退出...", "warning", log_cb)
        return False, "任务已停止。"

    if running_data_payload and auth_token_for_upload:
        log_output("\nStep 3/3: Sending Running Data...", callback=log_cb)
        if progress_callback: progress_callback(70, 100, "准备上传跑步数据...")
        try:
            if config["START_TIME_EPOCH_MS"] is None:
                log_output(f"模拟等待跑步完成 {total_dur} 秒...", callback=log_cb)
                for i in range(total_dur):
                    if stop_check_cb and stop_check_cb():
                        log_output("任务被请求停止，正在退出...", "warning", log_cb)
                        return False, "任务已停止。"
                    if progress_callback:
                        progress_callback(70 + int(20 * (i + 1) / total_dur), 100,
                                          f"等待跑步完成 ({i + 1}/{total_dur}秒)")
                    time.sleep(1)
            else:
                log_output("设置了过去的跑步时间，直接准备上传，短暂停顿 3 秒...", callback=log_cb)
                if progress_callback: progress_callback(80, 100, "短暂停顿...")
                if stop_check_cb and stop_check_cb():
                    log_output("任务被请求停止，正在退出...", "warning", log_cb)
                    return False, "任务已停止。"
                time.sleep(3)

            rt = 0
            max_rt = 3
            while rt < max_rt:
                if stop_check_cb and stop_check_cb():
                    log_output("任务被请求停止，正在退出...", "warning", log_cb)
                    return False, "任务已停止。"

                log_output(f"Attempting to upload running data (Attempt {rt + 1}/{max_rt})...", callback=log_cb)
                if progress_callback: progress_callback(90 + int(5 * rt / max_rt), 100,
                                                        f"上传数据 (尝试 {rt + 1}/{max_rt})...")

                response = upload_running_data(
                    config,
                    auth_token_for_upload,
                    running_data_payload,
                    log_cb=log_cb,
                    stop_check_cb=stop_check_cb
                )

                if response.get('code') == 0 and response.get('data'):
                    log_output("\nSUCCESS: Running data uploaded successfully with full data response!",
                               callback=log_cb)
                    if progress_callback: progress_callback(100, 100, "上传成功！")
                    return True, "上传成功！"
                elif response.get('code') == 0:
                    log_output(
                        f"\nWARNING: Uploaded, but response code is 0 with empty data. Server might still process it. Retrying in 3 seconds... (Attempt {rt + 1}/{max_rt})",
                        "warning", log_cb)
                    rt += 1
                    time.sleep(3)
                    if stop_check_cb and stop_check_cb():
                        log_output("任务被请求停止，正在退出...", "warning", log_cb)
                        return False, "任务已停止。"
                else:
                    log_output(
                        f"\nERROR: Upload returned non-success code ({response.get('code', 'N/A')}). No further retries for this attempt.",
                        "error", log_cb)
                    if progress_callback: progress_callback(100, 100, "上传失败！")
                    return False, f"上传失败，响应代码: {response.get('code', 'N/A')}"
            else:
                log_output("\nERROR: Upload failed or returned error code after retries.", "error", log_cb)
                if progress_callback: progress_callback(100, 100, "上传失败！")
                return False, "上传失败或返回错误代码 (达到最大重试次数)"
        except SportsUploaderError as e:
            log_output(f"Failed to send running data: {e}", "error", log_cb)
            if progress_callback: progress_callback(100, 100, "上传失败！")
            return False, str(e)
        except Exception as e:
            log_output(f"An unexpected error occurred during data upload: {e}", "error", log_cb)
            if progress_callback: progress_callback(100, 100, "上传失败！")
            return False, str(e)
    else:
        log_output("Skipping data upload due to missing generated data or authorization token.", "error", log_cb)
        if progress_callback: progress_callback(100, 100, "上传被跳过！")
        return False, "数据生成或认证失败，上传被跳过。"


if __name__ == "__main__":
    test_config = {
        "COOKIE": "your_keepalive_and_jsessionid_cookie_string_here",
        "USER_ID": "your_user_id",
        "START_LATITUDE": 31.031599,
        "START_LONGITUDE": 121.442938,
        "END_LATITUDE": 31.026400,
        "END_LONGITUDE": 121.455100,
        "RUNNING_SPEED_MPS": 2.5,
        "INTERVAL_SECONDS": 3,
        "START_TIME_EPOCH_MS": None,
        "HOST": "pe.sjtu.edu.cn",
        "UID_URL": "https://pe.sjtu.edu.cn/sports/my/uid",
        "MY_DATA_URL": "https://pe.sjtu.edu.cn/sports/my/data",
        "POINT_RULE_URL": "https://pe.sjtu.edu.cn/api/running/point-rule",
        "UPLOAD_URL": "https://pe.sjtu.edu.cn/api/running/result/upload"
    }

    def simple_log_cb(message, level):
        print(f"[{level.upper()}] {message}")

    def simple_progress_cb(current, total, message):
        print(f"Progress: {message} ({current}/{total})")

    success, msg = run_sports_upload(test_config, progress_callback=simple_progress_cb, log_cb=simple_log_cb, stop_check_cb=lambda: False)
    print(f"\nOperation {'SUCCESS' if success else 'FAILED'}: {msg}")
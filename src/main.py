import time
import datetime
from src.api_client import get_authorization_token_and_rules, upload_running_data
from src.data_generator import generate_running_data_payload
from utils.auxiliary_util import log_output, SportsUploaderError, get_current_epoch_ms


def run_sports_upload(config, progress_callback=None, log_cb=None, stop_check_cb=None):

    if stop_check_cb and stop_check_cb():
        return False, "任务已停止。"

    auth_token_for_upload = None

    try:
        log_output("步骤 1/3: 获取认证...", callback=log_cb)
        if progress_callback: progress_callback(10, 100, "获取认证信息...")

        if stop_check_cb and stop_check_cb():
            return False, "任务已停止。"

        auth_token_for_upload, _ = get_authorization_token_and_rules(config, log_cb=log_cb, stop_check_cb=stop_check_cb)

    except SportsUploaderError as e:
        return False, str(e)
    except Exception as e:
        return False, str(e)

    if stop_check_cb and stop_check_cb():
        return False, "任务已停止。"

    log_output("\n步骤 2/3: 生成跑步数据...", callback=log_cb)
    if progress_callback: progress_callback(40, 100, "生成跑步数据...")
    running_data_payload = None
    try:
        running_data_payload, total_dist, total_dur = generate_running_data_payload(
            config, [], {}, log_cb=log_cb, stop_check_cb=stop_check_cb
        )

    except SportsUploaderError as e:
        log_output(f"生成失败: {e}", "error", log_cb)
        return False, str(e)
    except Exception as e:
        log_output(f"错误: {e}", "error", log_cb)
        return False, str(e)

    if stop_check_cb and stop_check_cb():
        return False, "任务已停止。"

    if running_data_payload and auth_token_for_upload:
        log_output("\n步骤 3/3: 上传跑步数据...", callback=log_cb)
        total_runs = 25
        success_count = 0
        fail_count = 0

        now = datetime.datetime.now()
        yesterday = (now - datetime.timedelta(days=1)).replace(hour=8, minute=0, second=0, microsecond=0)
        start_times = [(yesterday - datetime.timedelta(days=i)).replace(hour=8, minute=0, second=0, microsecond=0) for i in range(total_runs)]

        for idx, start_dt in enumerate(start_times, start=1):
            if stop_check_cb and stop_check_cb():
                return False, "任务已停止。"

            config["START_TIME_EPOCH_MS"] = int(start_dt.timestamp() * 1000)

            try:
                log_output(f"生成第{idx}/{total_runs}条，时间: {start_dt}", callback=log_cb)
                running_data_payload, total_dist, total_dur = generate_running_data_payload(
                    config, [], {}, log_cb=log_cb, stop_check_cb=stop_check_cb
                )
            except SportsUploaderError as e:
                log_output(f"生成失败（{idx}/{total_runs}）: {e}", "error", log_cb)
                fail_count += 1
                log_output(f"已完成{idx}/{total_runs}", "info", log_cb)
                if progress_callback: progress_callback(idx, total_runs, f"已完成{idx}/{total_runs}")
                continue
            except Exception as e:
                log_output(f"错误（{idx}/{total_runs}）: {e}", "error", log_cb)
                fail_count += 1
                log_output(f"已完成{idx}/{total_runs}", "info", log_cb)
                if progress_callback: progress_callback(idx, total_runs, f"已完成{idx}/{total_runs}")
                continue

            try:
                log_output(f"上传第{idx}/{total_runs}条...", callback=log_cb)
                response = upload_running_data(
                    config,
                    auth_token_for_upload,
                    running_data_payload,
                    log_cb=log_cb,
                    stop_check_cb=stop_check_cb
                )

                if response.get('code') == 0 and response.get('data'):
                    log_output(f"第{idx}/{total_runs}条上传成功", "success", log_cb)
                    success_count += 1
                else:
                    log_output(f"{idx}/{total_runs} 未成功: {response}", "warning", log_cb)
                    fail_count += 1

            except SportsUploaderError as e:
                log_output(f"上传失败（{idx}/{total_runs}）: {e}", "error", log_cb)
                fail_count += 1
            except Exception as e:
                log_output(f"错误（{idx}/{total_runs}）: {e}", "error", log_cb)
                fail_count += 1

            log_output(f"已完成{idx}/{total_runs}", "info", log_cb)
            if progress_callback: progress_callback(idx, total_runs, f"已完成{idx}/{total_runs}")

        # 全部处理完成
        final_msg = f"完成: {success_count}/{total_runs} 成功, {fail_count}/{total_runs} 失败"
        log_output(final_msg, callback=log_cb)
        if progress_callback: progress_callback(total_runs, total_runs, "已完成")
        return True, final_msg
    else:
        log_output("数据生成或认证失败，跳过上传。", "error", log_cb)
        if progress_callback: progress_callback(100, 100, "已跳过")
        return False, "数据生成或认证失败。"
import os
import signal

import psutil
import sentry_sdk

LIMIT = 300_000_000  # 300 MB.

sentry_sdk.init(dsn=os.environ["SENTRY_DSN"])


def main():
    restarted_proc: int | None = None

    celery_procs = [
        process for process in psutil.process_iter()
        if "celery" in process.name()
    ]
    for proc in celery_procs:
        try:
            rss = proc.memory_info().rss
            print(f"'{proc.pid} {proc.name()}' rss: {rss}")
            if rss > LIMIT:
                print(f"WARNING: restarting '{proc}' '{proc.cmdline()}'")
                proc.send_signal(signal.SIGHUP)
                restarted_proc = proc.pid
                break
                # If there are multiple leaky procs, handle the next one
                # when this runs according to schedule.
        except Exception as e:
            print(f"error handling '{proc}': {e}")

    if restarted_proc is not None:
        raise RuntimeError(
            f"had to force restart Celery process {restarted_proc}")


if __name__ == "__main__":
    main()

import signal

import psutil

LIMIT = 200_000_000  # 200 MB.


def main():
    celery_procs = [
        process for process in psutil.process_iter()
        if "celery" in process.name()
    ]
    for proc in celery_procs:
        try:
            rss = proc.memory_info().rss
            print(f"'{proc.pid} {proc.name}' memory usage: {rss}")
            if rss > LIMIT:
                print(f"WARNING: restarting '{proc}' '{proc.cmdline()}'")
                proc.send_signal(signal.SIGHUP)
        except Exception as e:
            print(f"error handling '{proc}': {e}")


if __name__ == "__main__":
    main()

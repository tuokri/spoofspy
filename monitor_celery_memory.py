import psutil

LIMIT = 200000  # 200 MB.


def main():
    celery_procs = [
        process for process in psutil.process_iter()
        if "celery" in process.name()
    ]
    for proc in celery_procs:
        try:
            rss = proc.memory_info().rss
            print(f"'{proc}' '{proc.cmdline()}' memory usage: {rss}")
        except Exception as e:
            print(f"error handling '{proc}': {e}")


if __name__ == "__main__":
    main()

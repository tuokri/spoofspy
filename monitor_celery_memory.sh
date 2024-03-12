echo "starting celery memory monitoring"
while sleep 120; do
  echo "checking celery memory usage"
  python ./monitor_celery_memory.py
done

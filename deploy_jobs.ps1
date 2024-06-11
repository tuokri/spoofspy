hatch dep show requirements >requirements-jobs.txt
fly deploy --dockerfile .\Dockerfile-jobs `
    --config fly.jobs.toml -a spoofspy-jobs --verbose
fly ssh console --command "sysctl -w net.ipv4.ping_group_range='0 2147483647'" -a spoofspy-jobs
fly ssh console --command "sysctl -p --system" -a spoofspy-jobs

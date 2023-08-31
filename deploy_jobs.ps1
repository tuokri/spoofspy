hatch dep show requirements >requirements-jobs.txt
fly deploy --region ams --dockerfile .\Dockerfile-jobs `
    --config fly.jobs.toml -a spoofspy-jobs --verbose

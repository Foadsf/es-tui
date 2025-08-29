REM 1) Verify docker client is on PATH
where docker || (echo [ERROR] Docker CLI not found. Install Docker Desktop first. & exit /b 1)

REM 2) Try to talk to the daemon
docker info >NUL 2>&1
IF %ERRORLEVEL% NEQ 0 (
  echo [INFO] Docker daemon not reachable. Starting Docker Desktop as Administrator...
  powershell -NoProfile -Command ^
    "$p='C:\Program Files\Docker\Docker\Docker Desktop.exe';" ^
    "if (-not (Get-Process -Name 'Docker Desktop' -ErrorAction SilentlyContinue)) { Start-Process $p -Verb RunAs }"

  echo [INFO] Waiting for Docker daemon to become available...
  for /L %%I in (1,1,60) do (
    docker info >NUL 2>&1 && (echo [OK] Docker is up. & goto :docker_up)
    timeout /t 3 >NUL
  )
  echo [ERROR] Docker failed to start within timeout. Open Docker Desktop GUI and check WSL2/Hyper-V settings.
  exit /b 1
)

:docker_up
docker version
echo [OK] Docker client and server are reachable.

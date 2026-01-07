# 本地后端启动脚本

Write-Host "=== 本地后端启动脚本 ===" -ForegroundColor Green

# 检查端口占用
Write-Host "`n[1/4] 检查端口 5001 占用情况..." -ForegroundColor Yellow
$port5001 = netstat -ano | findstr :5001
if ($port5001) {
    Write-Host "⚠️  端口 5001 已被占用" -ForegroundColor Red
    Write-Host "请选择操作：" -ForegroundColor Yellow
    Write-Host "  1. 停止占用端口的进程（需要管理员权限）"
    Write-Host "  2. 使用其他端口（如 8000）"
    $choice = Read-Host "请输入选择 (1/2)"
    
    if ($choice -eq "1") {
        $pid = (netstat -ano | findstr :5001 | Select-Object -First 1).Split()[-1]
        if ($pid) {
            Write-Host "正在停止进程 $pid..." -ForegroundColor Yellow
            Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
            Start-Sleep -Seconds 2
            Write-Host "✓ 进程已停止" -ForegroundColor Green
        }
    } elseif ($choice -eq "2") {
        $PORT = 8000
        Write-Host "将使用端口 $PORT" -ForegroundColor Green
    } else {
        $PORT = 5001
        Write-Host "将尝试使用端口 5001" -ForegroundColor Yellow
    }
} else {
    $PORT = 5001
    Write-Host "✓ 端口 5001 可用" -ForegroundColor Green
}

# 检查 Docker 容器
Write-Host "`n[2/4] 检查 Docker 容器状态..." -ForegroundColor Yellow
$hadoopRunning = docker ps | Select-String "hadoop-namenode"
$neo4jRunning = docker ps | Select-String "kg-neo4j"

if (-not $hadoopRunning) {
    Write-Host "⚠️  Hadoop NameNode 容器未运行" -ForegroundColor Red
    Write-Host "请先启动: docker-compose up -d hadoop-namenode" -ForegroundColor Yellow
} else {
    Write-Host "✓ Hadoop NameNode 运行中" -ForegroundColor Green
}

if (-not $neo4jRunning) {
    Write-Host "⚠️  Neo4j 容器未运行" -ForegroundColor Red
    Write-Host "请先启动: docker-compose up -d neo4j" -ForegroundColor Yellow
} else {
    Write-Host "✓ Neo4j 运行中" -ForegroundColor Green
}

# 检查虚拟环境
Write-Host "`n[3/4] 检查 Python 环境..." -ForegroundColor Yellow
if (Test-Path "venv\Scripts\Activate.ps1") {
    Write-Host "✓ 虚拟环境存在" -ForegroundColor Green
    & "venv\Scripts\Activate.ps1"
} else {
    Write-Host "⚠️  虚拟环境不存在，使用系统 Python" -ForegroundColor Yellow
}

# 检查依赖
Write-Host "`n[4/4] 检查关键依赖..." -ForegroundColor Yellow
$fastapi = python -c "import fastapi; print('ok')" 2>$null
if ($fastapi) {
    Write-Host "✓ FastAPI 已安装" -ForegroundColor Green
} else {
    Write-Host "⚠️  FastAPI 未安装，正在安装..." -ForegroundColor Yellow
    pip install -r requirements-minimal.txt
}

# 启动服务
Write-Host "`n=== 启动后端服务 ===" -ForegroundColor Green
Write-Host "服务地址: http://localhost:$PORT" -ForegroundColor Cyan
Write-Host "Swagger UI: http://localhost:$PORT/docs" -ForegroundColor Cyan
Write-Host "`n按 Ctrl+C 停止服务`n" -ForegroundColor Yellow

if ($PORT -eq 5001) {
    uvicorn backend.app:app --host 0.0.0.0 --port 5001 --reload
} else {
    uvicorn backend.app:app --host 0.0.0.0 --port $PORT --reload
}


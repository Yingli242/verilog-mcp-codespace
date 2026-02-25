  #!/bin/bash
  echo "🔄 安装Python依赖..."
  pip install -r requirements.txt

  echo "🔍 检查工具..."
  which gcc && gcc --version | head -1
  which iverilog && iverilog --version | head -1
  which verilator && verilator --version | head -1

  echo "🚀 启动MCP服务器..."
  python mcp_server.py



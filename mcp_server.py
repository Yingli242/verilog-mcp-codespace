#!/usr/bin/env python3
  """
  GitHub Codespaces MCP Server for Verilog/C Execution
  运行在端口 8000，Claude 可直接调用
  """

  import subprocess
  import tempfile
  import os
  import json
  import sys
  from fastapi import FastAPI, HTTPException
  from pydantic import BaseModel
  import uvicorn

  app = FastAPI(title="Codespaces MCP Server")

  class ToolRequest(BaseModel):
      code: str = ""
      files: dict = {}
      testbench: str = "tb"
      args: str = ""

  @app.get("/health")
  def health():
      return {"status": "healthy", "service": "codespaces-mcp"}

  @app.get("/mcp/tools")
  def list_tools():
      return {
          "tools": [
              {
                  "name": "compile_and_run_c",
                  "description": "编译并运行C代码（gcc）",
                  "inputSchema": {
                      "type": "object",
                      "properties": {
                          "code": {"type": "string", "description": "C源代码"},
                          "args": {"type": "string", "description": "命令行参数"}
                      },
                      "required": ["code"]
                  }
              },
              {
                  "name": "run_verilog_simulation",
                  "description": "运行Verilog/SystemVerilog仿真（iverilog）",
                  "inputSchema": {
                      "type": "object",
                      "properties": {
                          "files": {
                              "type": "object",
                              "description": "文件名->代码映射，如 {\"counter.v\": \"module counter...\"}"
                          },
                          "testbench": {
                              "type": "string",
                              "description": "测试模块名",
                              "default": "tb"
                          }
                      },
                      "required": ["files"]
                  }
              }
          ]
      }

  @app.post("/mcp/tools/compile_and_run_c")
  async def run_c(request: ToolRequest):
      """执行C代码"""
      try:
          with tempfile.NamedTemporaryFile(mode='w', suffix='.c', delete=False) as f:
              f.write(request.code)
              c_file = f.name

          exe_file = c_file.replace('.c', '.out')

          # 编译
          compile_result = subprocess.run(
              ["gcc", c_file, "-o", exe_file, "-Wall", "-Wextra"],
              capture_output=True, text=True, timeout=30
          )

          if compile_result.returncode != 0:
              return {
                  "error": f"编译失败",
                  "stderr": compile_result.stderr,
                  "stdout": compile_result.stdout
              }

          # 运行
          run_args = [exe_file]
          if request.args:
              run_args.extend(request.args.split())

          run_result = subprocess.run(
              run_args,
              capture_output=True, text=True, timeout=30
          )

          # 清理
          os.unlink(c_file)
          os.unlink(exe_file)

          return {
              "success": True,
              "stdout": run_result.stdout,
              "stderr": run_result.stderr,
              "returncode": run_result.returncode
          }

      except subprocess.TimeoutExpired:
          return {"error": "执行超时（30秒限制）"}
      except Exception as e:
          return {"error": str(e)}

  @app.post("/mcp/tools/run_verilog_simulation")
  async def run_verilog(request: ToolRequest):
      """执行Verilog仿真"""
      try:
          temp_dir = tempfile.mkdtemp()
          file_paths = []

          # 保存所有文件
          for filename, content in request.files.items():
              if not filename.endswith(('.v', '.sv')):
                  filename = filename + '.v'
              filepath = os.path.join(temp_dir, filename)
              with open(filepath, 'w', encoding='utf-8') as f:
                  f.write(content)
              file_paths.append(filepath)

          # 检查iverilog
          try:
              subprocess.run(["iverilog", "--version"], capture_output=True, check=True)
          except:
              return {"error": "iverilog未安装，请在Codespaces中运行: sudo apt install iverilog"}

          # 编译
          out_file = os.path.join(temp_dir, "sim.out")
          compile_result = subprocess.run(
              ["iverilog", "-o", out_file, "-g2012"] + file_paths,
              capture_output=True, text=True, timeout=60
          )

          if compile_result.returncode != 0:
              return {
                  "error": "Verilog编译失败",
                  "stderr": compile_result.stderr,
                  "stdout": compile_result.stdout
              }

          # 仿真
          sim_result = subprocess.run(
              ["vvp", out_file],
              capture_output=True, text=True, timeout=60
          )

          # 清理
          for f in file_paths:
              try:
                  os.unlink(f)
              except:
                  pass
          try:
              os.unlink(out_file)
              os.rmdir(temp_dir)
          except:
              pass

          return {
              "success": True,
              "stdout": sim_result.stdout,
              "stderr": sim_result.stderr,
              "returncode": sim_result.returncode
          }

      except subprocess.TimeoutExpired:
          return {"error": "仿真超时（60秒限制）"}
      except Exception as e:
          return {"error": str(e)}

  @app.post("/mcp/call")
  async def mcp_call(request: dict):
      """MCP协议兼容端点"""
      if request.get("method") == "tools/list":
          tools_data = []
          for tool in list_tools()["tools"]:
              tools_data.append({
                  "name": tool["name"],
                  "description": tool["description"],
                  "inputSchema": tool["inputSchema"]
              })
          return {"result": {"tools": tools_data}}

      elif request.get("method") == "tools/call":
          params = request.get("params", {})
          name = params.get("name", "")
          arguments = params.get("arguments", {})

          if name == "compile_and_run_c":
              req = ToolRequest(code=arguments.get("code", ""), args=arguments.get("args", ""))
              result = await run_c(req)
          elif name == "run_verilog_simulation":
              req = ToolRequest(files=arguments.get("files", {}), testbench=arguments.get("testbench", "tb"))
              result = await run_verilog(req)
          else:
              return {"error": f"未知工具: {name}"}

          return {
              "result": {
                  "content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False, indent=2)}]
              }
          }

      return {"error": f"未知方法: {request.get('method')}"}

  if __name__ == "__main__":
      print("🚀 GitHub Codespaces MCP 服务器启动中...")
      print("📦 已安装工具: gcc, iverilog")
      print("🌐 服务器将在 http://localhost:8000 运行")
      print("🔧 可用端点:")
      print("  GET  /health")
      print("  GET  /mcp/tools")
      print("  POST /mcp/tools/{tool_name}")
      print("  POST /mcp/call")
      print("\n📡 等待 Claude 连接...")

      uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")

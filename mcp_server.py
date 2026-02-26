#!/usr/bin/env python3
  import subprocess, tempfile, os
  from fastapi import FastAPI
  import uvicorn

  app = FastAPI()

  @app.get("/health")
  def health():
      return {"status": "ok"}

  @app.get("/mcp/tools")
  def tools():
      return {"tools": []}

  @app.post("/mcp/tools/compile_and_run_c")
  async def run_c(code: str):
      try:
          with tempfile.NamedTemporaryFile(mode='w', suffix='.c', delete=False) as f:
              f.write(code)
              c_file = f.name
          exe_file = c_file.replace('.c', '.out')
          result = subprocess.run(["gcc", c_file, "-o", exe_file], capture_output=True, text=True)
          if result.returncode == 0:
              run_result = subprocess.run([exe_file], capture_output=True, text=True)
              output = run_result.stdout
          else:
              output = result.stderr
          os.unlink(c_file)
          if os.path.exists(exe_file):
              os.unlink(exe_file)
          return {"output": output}
      except Exception as e:
          return {"error": str(e)}

  if __name__ == "__main__":
      print("简易MCP服务器启动...")
      uvicorn.run(app, host="0.0.0.0", port=8000)

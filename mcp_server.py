#!/usr/bin/env python3
"""
GitHub Codespaces MCP Server - Enhanced Version
"""

import subprocess
import tempfile
import os
import json
import re
import contextlib
from pathlib import Path
from typing import Dict, Optional
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field, validator
import uvicorn

app = FastAPI(title="Codespaces MCP Server", version="1.0.0")

class ToolRequest(BaseModel):
    code: str = Field("", description="Source code to execute")
    files: Dict[str, str] = Field(default_factory=dict, description="File contents")
    testbench: str = Field("tb", description="Testbench module name")
    args: str = Field("", description="Command line arguments")
    
    @validator('code')
    def validate_code_length(cls, v):
        if len(v) > 10 * 1024 * 1024:  # 10MB limit
            raise ValueError("Code too large (max 10MB)")
        return v

@app.get("/")
async def root():
    return {
        "name": "Codespaces MCP Server",
        "version": "1.0.0",
        "description": "MCP server for code execution in GitHub Codespaces",
        "endpoints": [
            "/health",
            "/mcp/tools",
            "/mcp/tools/compile_and_run_c",
            "/mcp/tools/run_verilog_simulation",
            "/docs"
        ]
    }

@app.get("/health")
async def health():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "services": {
            "gcc": check_tool("gcc --version"),
            "iverilog": check_tool("iverilog -V"),
            "vvp": check_tool("vvp -V")
        }
    }

def check_tool(cmd: str) -> bool:
    """Check if a tool is available"""
    try:
        result = subprocess.run(
            cmd.split(), 
            capture_output=True, 
            text=True,
            timeout=5
        )
        return result.returncode == 0
    except:
        return False

@contextlib.contextmanager
def cleanup_files(*files):
    """Context manager for cleaning up temporary files"""
    try:
        yield
    finally:
        for file in files:
            try:
                if os.path.exists(file):
                    os.unlink(file)
            except:
                pass

@app.post("/mcp/tools/compile_and_run_c")
async def run_c(request: ToolRequest):
    """Compile and execute C code"""
    if not request.code.strip():
        raise HTTPException(status_code=400, detail="No code provided")
    
    try:
        # Create temporary C file
        with tempfile.NamedTemporaryFile(
            mode='w', 
            suffix='.c', 
            delete=False, 
            encoding='utf-8'
        ) as f:
            f.write(request.code)
            c_file = f.name
        
        exe_file = c_file.replace('.c', '.out')
        
        # Clean up temporary files on exit
        with cleanup_files(c_file, exe_file):
            # Compile C code
            compile_result = subprocess.run(
                ["gcc", c_file, "-o", exe_file, "-Wall", "-Wextra", "-O2"],
                capture_output=True, 
                text=True, 
                timeout=30
            )
            
            if compile_result.returncode != 0:
                return {
                    "success": False,
                    "error": "Compilation failed",
                    "compiler_output": compile_result.stderr
                }
            
            # Execute the compiled binary
            run_result = subprocess.run(
                [exe_file] + (request.args.split() if request.args else []),
                capture_output=True, 
                text=True, 
                timeout=30
            )
            
            return {
                "success": True,
                "compilation": {
                    "returncode": compile_result.returncode,
                    "stderr": compile_result.stderr
                },
                "execution": {
                    "returncode": run_result.returncode,
                    "stdout": run_result.stdout,
                    "stderr": run_result.stderr
                }
            }
            
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=408, detail="Execution timeout")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import datetime
    
    config = {
        "host": os.getenv("MCP_HOST", "0.0.0.0"),
        "port": int(os.getenv("MCP_PORT", 8000)),
        "log_level": os.getenv("LOG_LEVEL", "info")
    }
    
    print(f"""
    ===========================================
    MCP Server Starting...
    Time: {datetime.datetime.now().isoformat()}
    Host: {config['host']}:{config['port']}
    ===========================================
    """)
    
    uvicorn.run(
        app, 
        host=config["host"], 
        port=config["port"],
        log_level=config["log_level"]
    )

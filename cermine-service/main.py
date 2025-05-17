#!/usr/bin/env python3
import os
import shutil
import subprocess
import uuid
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse

app = FastAPI(title="CERMINE Service")

# Path to the CERMINE fat-jar in the container
CERMINE_JAR = os.getenv("CERMINE_JAR_PATH", "/cermine.jar")
# How long (in seconds) to allow CERMINE to run
CERMINE_TIMEOUT = int(os.getenv("CERMINE_TIMEOUT", "300"))

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post("/parse")
async def parse_pdf(file: UploadFile = File(...)):
    # Create a unique working directory
    job_id = uuid.uuid4().hex
    workdir = f"/tmp/{job_id}"
    os.makedirs(workdir, exist_ok=True)

    # Save uploaded PDF
    input_path = os.path.join(workdir, file.filename)
    with open(input_path, "wb") as f:
        f.write(await file.read())

    # Invoke CERMINE to produce JATS output
    cmd = [
        "java", "-jar", CERMINE_JAR,
        "-path", workdir,
        "-outputs", "jats"
    ]
    try:
        proc = subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=CERMINE_TIMEOUT
        )
    except subprocess.TimeoutExpired:
        shutil.rmtree(workdir)
        raise HTTPException(status_code=504, detail="CERMINE processing timed out")
    except subprocess.CalledProcessError as e:
        shutil.rmtree(workdir)
        stderr = e.stderr.decode(errors="ignore")
        raise HTTPException(status_code=500, detail=f"CERMINE error: {stderr}")

    # Locate generated JATS file (.nxml or .xml)
    output_file = None
    for name in os.listdir(workdir):
        if name.lower().endswith((".nxml", ".xml")):
            output_file = os.path.join(workdir, name)
            break

    if not output_file:
        shutil.rmtree(workdir)
        raise HTTPException(status_code=500, detail="No output file produced by CERMINE")

    # Read and return
    with open(output_file, "r", encoding="utf-8") as f:
        content = f.read()

    # Clean up
    shutil.rmtree(workdir)
    return {"jats": content}
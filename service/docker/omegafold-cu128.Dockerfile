FROM pytorch/pytorch:2.7.1-cuda12.8-cudnn9-runtime

# Build context must contain, beside this file:
#
#   src/service.py            from /app/tools/OmegaFold/service.py in the cu121 image
#   src/template/             from /app/tools/template
#   src/utils.py              from /app/tools/utils.py
#   omegafold/                from /usr/local/lib/python3.10/dist-packages/omegafold
#
# All four come out of `docker create` plus `docker cp` against igem-silk/omegafold:latest;
# extracting them is faster than rebuilding OmegaFold, and it keeps the service code identical
# across the two machines so that a prediction means the same thing on both.
#
# The workstation image builds on CUDA 12.1, whose PyTorch carries no kernels for sm_120 — the
# architecture of this machine's GPU. Loading the model there fails with "no kernel image is
# available for execution on the device". Nothing else about that image is architecture bound:
# the service code, the OmegaFold package and the weights are all portable, so only the layer
# that is not gets rebuilt here.
#
# OmegaFold is copied rather than installed. Its setup.py refuses any interpreter but 3.10, and
# this base image ships 3.11; the package itself is pure Python with no compiled extensions, so
# the installed copy from the workstation image runs unchanged on a newer interpreter.

RUN apt-get update && apt-get install -y --no-install-recommends \
        git curl build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m pip install --no-cache-dir --upgrade pip setuptools wheel \
    && python3 -m pip install --no-cache-dir biopython \
    && python3 -m pip install --no-cache-dir fastapi "uvicorn[standard]" pydantic

COPY omegafold /opt/conda/lib/python3.11/site-packages/omegafold

# Same layout the service expects: it locates the template package by walking three levels up
# from its own file, so service.py must sit in /app/tools/OmegaFold.
COPY src/service.py /app/tools/OmegaFold/service.py
COPY src/template /app/tools/template
COPY src/utils.py /app/tools/utils.py

WORKDIR /app/tools/OmegaFold

ENV PORT=8204
ENV OMEGAFOLD_CACHE=/app/tools/models/omegafold
ENV PYTHONUNBUFFERED=1

EXPOSE 8204
CMD ["python3", "service.py"]

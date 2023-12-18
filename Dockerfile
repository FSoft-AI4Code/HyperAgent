# Builds GPU docker image of PyTorch
# Uses multi-staged approach to reduce size
# Stage 1
# Use base conda image to reduce time
FROM continuumio/miniconda3:latest AS compile-image
# Specify py version
ENV PYTHON_VERSION=3.10

RUN apt-get update && \
    apt-get install -y curl git wget software-properties-common git-lfs && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists*

# Install Go
RUN wget https://dl.google.com/go/go1.17.2.linux-amd64.tar.gz
RUN tar -xvf go1.17.2.linux-amd64.tar.gz
RUN mv go /usr/local

ENV GOROOT=/usr/local/go
ENV GOPATH=$HOME/go
ENV PATH=$GOPATH/bin:$GOROOT/bin:$PATH

# Install Zoekt
RUN go get github.com/sourcegraph/zoekt/
RUN go get github.com/sourcegraph/zoekt/cmd/zoekt-index
RUN go install github.com/sourcegraph/zoekt/cmd/zoekt-index
RUN go get github.com/sourcegraph/zoekt/cmd/zoekt-webserver
RUN go install github.com/sourcegraph/zoekt/cmd/zoekt-webserver

# Install universal-ctags for semantic code search
RUN apt-get update && \
    apt-get install -y autoconf pkg-config && \
    git clone https://github.com/universal-ctags/ctags.git && \
    cd ctags && \
    ./autogen.sh && \
    ./configure --program-prefix=universal- --enable-json && \
    make && \
    make install

ENV CTAGS_COMMAND=universal-ctags

# Create our conda env - copied from https://github.com/huggingface/accelerate/blob/main/docker/accelerate-gpu/Dockerfile
RUN conda create --name repopilot python=${PYTHON_VERSION} ipython jupyter pip
RUN python3 -m pip install --no-cache-dir --upgrade pip

# Below is copied from https://github.com/huggingface/accelerate/blob/main/docker/accelerate-gpu/Dockerfile
# We don't install pytorch here yet since CUDA isn't available
# instead we use the direct torch wheel
ENV PATH /opt/conda/envs/repopilot/bin:$PATH
# Activate our bash shell
RUN chsh -s /bin/bash
SHELL ["/bin/bash", "-c"]

# Stage 2
FROM nvidia/cuda:12.2.2-devel-ubuntu22.04 AS build-image
COPY --from=compile-image /opt/conda /opt/conda
ENV PATH /opt/conda/bin:$PATH

RUN chsh -s /bin/bash
COPY requirements.txt .
SHELL ["/bin/bash", "-c"]
RUN source activate repopilot && \ 
    python3 -m pip install --no-cache-dir -r requirements.txt

# Install apt libs
RUN apt-get update && \
    apt-get install -y curl git wget && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists*

COPY . /repopilot
WORKDIR /repopilot

RUN source activate repopilot && \
    python3 -m pip install --no-cache-dir -e .

# Activate the virtualenv
CMD ["/bin/bash"]
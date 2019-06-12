FROM ubuntu:18.04 as souffle
RUN apt-get -y update && apt-get -y install \
    automake \
    bison \
    build-essential \
    doxygen \
    flex \
    git \
    libffi-dev \
    libsqlite3-dev \
    libtool \
    make \
    mcpp \
    pkg-config \
    sqlite3 \
    zlib1g-dev \
&& rm -rf /var/lib/apt/lists/*

RUN git clone -b 1.5.1 https://github.com/souffle-lang/souffle
RUN cd souffle && sh ./bootstrap
RUN cd souffle && ./configure --prefix=/usr --enable-64bit-domain --disable-provenance
RUN cd souffle && make -j4 install
RUN cd souffle && cp include/souffle/RamTypes.h /usr/include/souffle/

FROM ubuntu:18.04

ARG CMAKE_VERSION=3.9
ARG CXX_COMPILER=g++-7

RUN apt-get -y update && apt-get -y install \
    autoconf \
    automake \
    bison \
    build-essential \
    clang \
    cmake \
    curl \
    doxygen \
    ed \
    flex \
    gdb \
    git \
    libncurses5-dev \
    libpcre3-dev \
    libsqlite3-dev \
    libtool \
    make \
    mcpp \
    pkg-config \
    python \
    python-pip \
    python3 \
    python3-pip \
    sqlite3 \
    wget \
    zlib1g-dev \
&& rm -rf /var/lib/apt/lists/*

RUN pip3 install setuptools

COPY --from=souffle /usr/bin/souffle-compile /usr/bin/souffle-compile
COPY --from=souffle /usr/bin/souffle-config /usr/bin/souffle-config
COPY --from=souffle /usr/bin/souffle /usr/bin/souffle
COPY --from=souffle /usr/bin/souffle-profile /usr/bin/souffle-profile
COPY --from=souffle /usr/include/souffle/ /usr/include/souffle

# Install capstone
RUN cd /usr/local/src \
    && wget https://github.com/aquynh/capstone/archive/4.0.1.tar.gz \
    && tar xf 4.0.1.tar.gz \
    && cd capstone-4.0.1 \
    && CAPSTONE_ARCHS=x86 ./make.sh \
    && CAPSTONE_ARCHS=x86 ./make.sh install

# Only copy files needed for the build
# COPY ./CMakeLists.boost /ddisasm/CMakeLists.boost
# COPY ./CMakeLists.txt /ddisasm/CMakeLists.txt
# COPY ./ddisasm /ddisasm/ddisasm
# COPY ./doc /ddisasm/doc
# COPY ./src /ddisasm/src
# COPY ./gtirb /ddisasm/gtirb
# COPY ./gtirb-pprinter /ddisasm/gtirb-pprinter

# Build GTIRB
RUN git clone https://git.grammatech.com/rewriting/gtirb.git /gtirb \
    && cd /gtirb \
    && git checkout PYTHON
RUN rm -rf /gtirb/build \
    /gtirb/CMakeCache.txt \
    /gtirb/CMakeFiles \
    /gtirb/CMakeScripts
WORKDIR /build/gtirb
RUN cmake /gtirb -DCMAKE_CXX_COMPILER=${CXX_COMPILER} \
    && make \
    && rm -rf /gtirb
ENV PATH=/build/gtirb/bin:$PATH
WORKDIR python
RUN python3 setup.py install

# Build gtirb-pprinter
RUN git clone https://git.grammatech.com/rewriting/gtirb-pprinter.git /gtirb-pprinter
RUN rm -rf /gtirb-pprinter/build \
    /gtirb-pprinter/CMakeCache.txt \
    /gtirb-pprinter/CMakeFiles \
    /gtirb-pprinter/CMakeScripts
WORKDIR /build/gtirb-pprinter
RUN cmake /gtirb-pprinter -DCMAKE_CXX_COMPILER=${CXX_COMPILER} \
    && make \
    && rm -rf /gtirb-pprinter
ENV PATH=/build/gtirb-pprinter/bin:$PATH

# Build ddisasm
ENV TERM xterm
RUN git clone https://git.grammatech.com/rewriting/ddisasm.git /ddisasm
RUN rm -rf /ddisasm/build \
    /ddisasm/CMakeCache.txt \
    /ddisasm/CMakeFiles \
    /ddisasm/CMakeScripts
WORKDIR /build/ddisasm
RUN cmake /ddisasm -DCMAKE_CXX_COMPILER=${CXX_COMPILER} -DCORES=8 \
    && make \
    && rm -rf /ddisasm
ENV PATH=/build/ddisasm/bin:$PATH

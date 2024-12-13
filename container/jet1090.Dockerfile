FROM ubuntu:20.04

RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates xz-utils libsoapysdr-dev && rm -rf /var/lib/apt/lists/*

# It's installed by root, at $HOME/.cargo/bin/jet1090
RUN curl --proto '=https' --tlsv1.2 -LsSf https://github.com/xoolive/rs1090/releases/download/v0.3.8/jet1090-installer.sh | sh
RUN mv $HOME/.cargo/bin/jet1090 /usr/local/bin/jet1090

RUN useradd -ms /bin/bash user
USER user
CMD jet1090 --help

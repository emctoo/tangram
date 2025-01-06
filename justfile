# set just environment variables
set dotenv-load
set positional-arguments
set export

# read from .env file
JET1090_PARAMS := env_var("JET1090_PARAMS")

# set default values
NETWORK := "tangram"
JET1090_VERSION := "v0.4.1"
JET1090_VOL := "jet1090-vol"
BASESTATION_ZIP_URL := env_var_or_default("BASESTATION_ZIP_URL", "https://jetvision.de/resources/sqb_databases/basestation.zip")


_default:
  @just _check-env
  @just --list

_check-env:
  #!/usr/bin/env bash

  if [ ! -f .env ]; then
    printf ".env file does not exist, use default configurations.\n\n"
  fi

# install watchexec, uv, process-compose
install-dependent-binaries:
  #!/usr/bin/env bash
  set -x -euo pipefail

  DEST_DIR="$HOME/.local/bin"

  cleanup() {
    rm -rf /tmp/watchexec*
  }
  trap cleanup EXIT

  LATEST_TAG=$(curl -sL https://api.github.com/repos/watchexec/watchexec/releases/latest | jq -r '.tag_name')
  DL_URL="https://github.com/watchexec/watchexec/releases/download/${LATEST_TAG}/watchexec-${LATEST_TAG#v}-x86_64-unknown-linux-musl.tar.xz"
  curl -L "$DL_URL" -o /tmp/watchexec.tar.xz
  mkdir -p $DEST_DIR
  tar -xvf /tmp/watchexec.tar.xz --strip-components=1 -C $DEST_DIR "watchexec-${LATEST_TAG#v}-x86_64-unknown-linux-musl/watchexec"
  echo "watchexec has been installed to $DEST_DIR/watchexec."

  curl -LsSf https://astral.sh/uv/install.sh | sh # uv
  echo "uv has been installed to $DEST_DIR/{uv,uvx}."

  sh -c "$(curl --location https://raw.githubusercontent.com/F1bonacc1/process-compose/main/scripts/get-pc.sh)" -- -d -b $DEST_DIR # process-compose
  echo "process-compose has been installed to $DEST_DIR/process-compose."

  ls -al $DEST_DIR

# create virtualenv
create-uv-venv wd="~/tangram/service":
  #!/usr/bin/env bash
  set -x -euo pipefail

  cd {{wd}}
  mkdir -p /home/user/.local/share/venvs

  # specify the path for virtual environment
  # by default it creates .venv in current working directory, which has issues of permission
  # https://docs.astral.sh/uv/concepts/projects/#configuring-the-project-environment-path
  export UV_PROJECT_ENVIRONMENT=/home/user/.local/share/venvs/tangram
  uv venv --verbose
  uv sync --dev --verbose --no-cache && uv cache clean

# create tangram network
network:
  #!/usr/bin/env bash
  set -x -euo pipefail

  if podman network exists {{NETWORK}}; then
    echo "network tangram exists"
    exit 0
  fi

  podman network create {{NETWORK}}

# launch redis
redis: network
  #!/usr/bin/env bash

  if podman container exists redis; then
    echo "container redis exists"
    exit 0
  fi

  podman container run -d --rm --name redis --network {{NETWORK}} -p 6379:6379 \
    docker.io/library/redis:8.0-M02

# watch current dir and run the service
# presumbly, you have uv installed and the virtualenv is created
tangram-service port="18000" host="0.0.0.0":
  #!/usr/bin/env bash
  set -x -euo pipefail

  pwd
  cd service
  watchexec -r -w . -e py -- \
    uv run uvicorn --host {{host}} --port {{port}} tangram.app:app --ws websockets --log-config logging.yml

tangram-web host="0.0.0.0" port="2024":
  #!/usr/bin/env bash

  echo "- checking env ..."
  env

  cd /home/user/tangram/web
  echo "- working directory: ${PWD}"

  if [ ! -f /tmp/npm-installed.txt ]; then
    echo "- removing node_modules ..."
    rm -rf node_modules

    echo "- npm install now ..."
    npm install --verbose
    npm install --dev --verbose

    touch /tmp/npm-installed.txt
  else
    echo "- node_modules exists, skip npm install."
  fi

  npx vite --host {{host}} --port {{port}}

# build process-compose based tangram image
build-tangram:
  podman image build -f container/tangram.Containerfile -t tangram:0.1 .

# launch tangram container
tangram: network
  #!/usr/bin/env bash

  if [ "$(uname)" = "Linux" ]; then \
    podman container run -it --rm --name tangram --network {{NETWORK}} -p 2024:2024 --env-file .env \
      --userns=keep-id \
      -e REDIS_URL=redis://redis:6379 \
      -v .:/home/user/tangram:z \
      tangram:0.1; \
  elif [ "$(uname)" = "Darwin" ]; then \
    # TODO: verify it's necessary to include `--userns=keep-id` here
    podman container run -it --rm --name tangram --network {{NETWORK}} -p 2024:2024 --env-file .env \
      --userns=keep-id --security-opt label=disable \
      -e REDIS_URL=redis://redis:6379 \
      -v $PWD:/home/user/tangram \
      tangram:0.1; \
  fi

# rate-limiting plugin container
rate-limiting: network
  podman container run -it --rm --name rate_limiting \
    --network {{NETWORK}} \
    -v .:/home/user/tangram:z --userns=keep-id --user $(id -u) \
    -e UV_PROJECT_ENVIRONMENT=/home/user/.local/share/venvs/tangram \
    -e REDIS_URL=redis://redis:6379 \
    -w /home/user/tangram/service \
    tangram:0.1 uv run -- python -m tangram.plugins.rate_limiting --dest-topic=coordinate

table:
  podman container run -it --rm --name rate_limiting \
    --network {{NETWORK}} \
    -v .:/home/user/tangram:z --userns=keep-id --user $(id -u) \
    -e UV_PROJECT_ENVIRONMENT=/home/user/.local/share/venvs/tangram \
    -e REDIS_URL=redis://redis:6379 \
    -w /home/user/tangram/service \
    tangram:0.1 uv run -- python -m tangram.plugins.table

log log="tangram": network
  @podman container exec -it -e TERM=xterm-256color -w /tmp/tangram tangram tail -f {{log}}.log

jet1090-basestation:
  #!/usr/bin/env bash

  mkdir -p ~/.cache/jet1090
  if [[ ! -f ~/.cache/jet1090/basestation.zip ]]; then
    echo "basestation.zip not found, downloading ..."
    curl -L {{BASESTATION_ZIP_URL}} -o ~/.cache/jet1090/basestation.zip
  fi

  unzip -o ~/.cache/jet1090/basestation.zip -d ~/.cache/jet1090

jet1090-vol: jet1090-basestation
  # Commands for creating a volume for basestation.sqb
  # It can be used as name volume when running jet1090 contaienr
  # FIXME: it does not work with jet1090 for now, it tries to create the directory and download anyway.
  tar czf ~/.cache/jet1090/basestation.sqb.tgz -C ~/.cache/jet1090 basestation.sqb
  podman volume create {{JET1090_VOL}}
  podman volume import {{JET1090_VOL}} ~/.cache/jet1090/basestation.sqb.tgz
  podman volume inspect {{JET1090_VOL}}

# build jet1090 image
build-jet1090:
  podman image build -t jet1090:{{JET1090_VERSION}} --build-arg VERSION={{JET1090_VERSION}} -f container/jet1090.Dockerfile .

# run jet1090 interactively, as a container
jet1090: network redis jet1090-basestation
  podman run -it --rm --name jet1090 \
    --network {{NETWORK}} -p 8080:8080 \
    -v ~/.cache/jet1090:/home/user/.cache/jet1090 --userns=keep-id \
    localhost/jet1090:{{JET1090_VERSION}} \
      jet1090 \
        -i \
        --serve-port 8080 \
        --redis-url redis://redis:6379 --redis-topic jet1090-full \
        {{JET1090_PARAMS}}

# run jet1090 (0.3.8) as a service
jet1090-daemon: network redis jet1090-basestation
  podman run -d --rm --name jet1090 \
    --network {{NETWORK}} -p 8080:8080 \
    -v ~/.cache/jet1090:/home/user/.cache/jet1090 --userns=keep-id \
    localhost/jet1090:{{JET1090_VERSION}} \
      jet1090 \
        --serve-port 8080 \
        --redis-url redis://redis:6379 --redis-topic jet1090-full \
        {{JET1090_PARAMS}}

#!/usr/bin/env bash

if [[ $# -ne 2 ]] ; then
    echo "Image not set or not found"
    exit 1
fi

OPTION=$1
IMAGE=$2

# Start docker.service before download/pull images
pull_image() {
  systemctl is-active --quiet docker

  if [ "$?" = "0" ]; then
      sudo docker pull ${IMAGE}
      exit 0
  else
      systemctl restart docker
      sudo docker pull ${IMAGE}
      systemctl stop docker.socket
  fi
}

# Start docker.service before delete images
remove_image() {
  systemctl is-active --quiet docker

  if [ "$?" = "0" ]; then
      sudo docker image rm ${IMAGE}
      exit 0
  else
      systemctl restart docker
      sudo docker image rm ${IMAGE}
      systemctl stop docker.socket
  fi
}

# Start docker.service before show images
show_images() {
  systemctl is-active --quiet docker

  if [ "$?" = "0" ]; then
      sudo docker image ls | egrep -v "REPOSITORY" | awk '{print $1}'
      exit 0
  else
      systemctl restart docker
      sudo docker image ls | egrep -v "REPOSITORY" | awk '{print $1}'
      systemctl stop docker.socket
  fi
}


if [ "$OPTION" = "--pull" ]; then
    pull_image
    exit 0
fi

if [ "$OPTION" = "--remove" ]; then
    remove_image
    exit 0
fi

if [ "$OPTION" = "--show-images" ]; then
    show_images
    exit 0
fi

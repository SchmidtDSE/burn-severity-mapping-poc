#!/bin/bash

curl -o "gcloud.tar.gz" "https://dl.google.com/dl/cloudsdk/channels/rapid/downloads/google-cloud-cli-457.0.0-linux-x86_64.tar.gz"
tar -xzf gcloud.tar.gz 
mv google-cloud-sdk /root
$HOME/google-cloud-sdk/install.sh --quiet
rm -rf gcloud.tar.gz
export PATH=$PATH:/root/google-cloud-sdk/bin

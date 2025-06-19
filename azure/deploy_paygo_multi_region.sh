#!/usr/bin/env bash
set -euo pipefail

################################ EDIT ################################
REPO=https://github.com/pedrotcp/az.git      # your repo
RG=coverRG
STOR=coverstore$RANDOM
VM_SIZE=Standard_F64s_v2          # 64 vCPU, fits under 65-core cap
REGIONS=(eastus eastus2 southcentralus westus3 northeurope westeurope \
         uksouth francecentral swedencentral southeastasia japaneast \
         brazilsouth canadacentral centralindia)
######################################################################

echo "==> RG + storage"
az group create -n $RG -l ${REGIONS[0]} -o none
az storage account create -g $RG -n $STOR -l ${REGIONS[0]} --sku Standard_LRS -o none
KEY=$(az storage account keys list -g $RG -n $STOR --query '[0].value' -o tsv)
az storage container create --account-name $STOR --account-key $KEY -n results -o none
SAS=$(az storage account generate-sas --account-name $STOR \
      --permissions acdlrw --services bf --resource-types sco \
      --expiry "$(date -u -d '+7 days' '+%Y-%m-%dT%H:%MZ')" -o tsv)

cat > cloud-init.yml <<EOF
#cloud-config
package_update: true
packages: [git, build-essential, python3.11, python3.11-venv, wget]

runcmd:
  - |
    set -e
    cd /opt

    # clone repo (private token already embedded in $REPO)
    git clone $REPO repo

    # create venv and install deps
    python3.11 -m venv /opt/venv
    /opt/venv/bin/pip install -q -r repo/requirements.txt

    # unique seed from hostname digits
    SEED=$(hostname | tr -dc '0-9')

    # run pipeline WITHOUT 'source'
    /opt/venv/bin/python repo/src/hg_greedy_seed.py --seed $SEED
    /opt/venv/bin/python repo/src/cp_sat_rowgen.py
    /opt/venv/bin/python repo/src/scip_branch_price.py
    /opt/venv/bin/python repo/src/proof_fullcover.py

    # upload result
    wget -q https://aka.ms/downloadazcopy-v10-linux -O az.tgz
    tar xf az.tgz --strip-components=1
    ./azcopy copy phaseC.json "https://$STOR.blob.core.windows.net/results/$(hostname)-phaseC.json?$SAS"
EOF

echo "==> launch pay-go VM per region (skips if quota/image unavailable)"
for R in "${REGIONS[@]}"; do
  (
    echo -n " • $R … "
    az vm create -g $RG -n cover-$R \
      --image "Canonical:0001-com-ubuntu-server-jammy:22_04-lts:latest" \
      --size $VM_SIZE --admin-username azureuser --generate-ssh-keys \
      --location $R --custom-data cloud-init.yml -o none \
      && echo "started" || echo "SKIPPED (quota or image)"
  ) &
done
wait
echo "+++ create requests finished"

echo
echo "### Watch blobs (give each VM 45–60 min)"
echo "az storage blob list -c results --account-name $STOR --account-key $KEY --query [].name"

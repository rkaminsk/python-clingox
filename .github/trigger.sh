#!/bin/bash

function list() {
    curl \
      -X GET \
      -H "Accept: application/vnd.github.v3+json" \
      "https://api.github.com/repos/potassco/python-clingox/actions/workflows" \
      -d "{\"ref\":\"ref\"}"
}

function dispatch() {
    token=$(grep -A1 workflow_dispatch ~/.tokens | tail -n 1)
    curl \
      -u "rkaminsk:$token" \
      -X POST \
      -H "Accept: application/vnd.github.v3+json" \
      "https://api.github.com/repos/potassco/python-clingox/actions/workflows/$1/dispatches" \
      -d "{\"ref\":\"$3\",\"inputs\":{\"wip\":\"$2\"${4:+,$4}}}"
}

branch=wip
wip=true

case $1 in
    list)
        list
        ;;
    release)
        if [[ $# < 2 ]]; then
            echo "usage: trigger release REF"
            exit 1
        fi
        wip=false
        branch=$2
        ;&
    dev)
        # .github/workflows/ppa-dev.yml
        dispatch 5997696 $wip $branch
        # .github/workflows/pipsource.yml
        dispatch 6065447 $wip $branch
        # .github/workflows/conda-dev.yml
        dispatch 6066933 $wip $branch
        ;;
    *)
        echo "usage: trigger {list,dev,release}"
        exit 1
        ;;
esac

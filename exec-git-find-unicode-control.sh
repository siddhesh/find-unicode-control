#!/bin/bash
# SPDX-License-Identifier: BSD-3-Clause

###
#
# Batch script to scan all files in branches and tags of
# a git repository.
#
# Both this script and the find-find_unicode_control.py script
# should be accessible from the PATH.
#
# Change directory into the local git directory to be scanned
# then execute this script with either:
# -a: scan all branches and tags
# -b: scan all branches
# -t: scan all tags
# -p PATTERN: scan all branches/tags that match PATTERN
#
###

get-branches() {
  # Ignore dependabot
  # Ignore pull requests
  local branches=$(git branch --remotes --format='%(refname:short)' | \
                    grep -v dependabot | \
                    grep -v 'pr/' | \
                    grep -v 'pull/')
  if [ -z "${branches}" ]; then
    echo >&2 echo "ERROR: cannot find any branches from ${PROD_REPO_ALIAS}"
    exit 1
  fi

  echo ${branches}
}

get-tags() {
  remotes=$(git remote | awk {'print $1'})
  local tags=""
  for remote in ${remotes}
  do
    # Ignore dependabot
    # Ignore pull requests
    local rtags=$(git ls-remote --tags "${remote}" | \
                   awk {'print $2'} | \
                   grep -v "{}" | \
                   grep -v 'pr/' | \
                   grep -v 'pull/' | \
                   sed 's/refs\///')
    tags="${tags} ${rtags}"
  done

  if [ -z "${tags}" ]; then
    echo >&2 echo "ERROR: cannot find any tags"
    exit 1
  fi

  echo ${tags}
}

get-branches-and-tags() {
  local branches=$(get-branches)
  local tags=$(get-tags)
  
  echo "${branches} ${tags}"
}

get-pattern() {
  local pattern="${1}"
  if [ -z "${pattern}" ]; then
    echo >&2 echo "ERROR: pattern not specified"
    exit 1
  fi

  local commits=$(git for-each-ref --format='%(refname)' | \
                    grep -v dependabot | \
                    grep -v 'pr/' | \
                    grep -v 'pull/' | \
                    grep "${pattern}" | \
                    sed -E -e 's/refs\///' | sed -E -e 's/remotes\///')
  if [ -z "${commits}" ]; then
    echo >&2 echo "ERROR: cannot find any branches or tags"
    exit 1
  fi

  echo ${commits}
}


#
# Check find_unicode_control is available
#
if ! command -v find_unicode_control.py &> /dev/null; then
  echo "ERROR: Please install the find_unicode_control.py script so it is accessible from any directory"
  exit 1
fi

#
# Fetch all tags from all remote repositories defined locally.
# Note: if tags are duplicated across repositories then this will
#       overwrite them. In this event you should checkout the overwritten
#       tag manually and scan it.
#
git fetch --tags --all -f
if [ $? != 0 ]; then
  echo "Warning: Problems occurred while fetching from all repositories"
fi

#
# Check which branches and tags are required to be scanned
#
while getopts ":atbp:" OPT; do
  case $OPT in
    a)
      ends=$(get-branches-and-tags)
      ;;
    b)
      ends=$(get-branches)
      ;;
    t)
      ends=$(get-tags)
      ;;
    p)
      ends=$(get-pattern ${OPTARG})
      ;;
   \?)
     echo "Invalid option: -$OPTARG" >&2
     ;;
  esac
done
shift $((OPTIND-1))

if [ -z "${ends}" ]; then
  echo "ERROR: No branches or tags specified"
  exit 1
fi

#
# Loop through the commits listed, check them out and scan the contents
#
for commit in ${ends}
do
  echo "Checking: $commit"

  status=$(git submodule deinit -f --all &> /dev/null && git checkout -f "${commit}" &> /dev/null && git submodule init &> /dev/null)
  if [ $? != 0 ]; then
    echo "ERROR occurred ... checking out ${commit}"
    exit 1
  fi

  find_unicode_control.py -p bidi .
  
done

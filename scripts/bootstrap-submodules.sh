#!/usr/bin/env bash
#
# Check out the vendored gear-genomics front-ends and verify that every pinned
# commit is actually reachable.
#
# The pins are not always on the upstream repository: componentising an app
# happens in a fork first, so `.gitmodules` may point at a fork and a pin may
# exist nowhere public yet. A plain `git submodule update --init` reports that
# as an opaque fetch failure, so this script names the submodule, the commit and
# the remote that is missing it.

set -euo pipefail

repo_root="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel)"
cd "$repo_root"

git submodule update --init --recursive || true

missing=0

while read -r path; do
    pinned="$(git ls-tree HEAD "$path" | awk '{print $3}')"
    url="$(git config -f .gitmodules --get "submodule.${path}.url")"

    if [ -z "$pinned" ]; then
        # Newly added submodule that HEAD does not know about yet.
        continue
    fi

    if git -C "$path" cat-file -e "${pinned}^{commit}" 2>/dev/null; then
        continue
    fi

    missing=1
    cat >&2 <<MSG

  ${path}
      pinned commit : ${pinned}
      declared url  : ${url}

      That commit is not in the local checkout. If it lives on a fork that is
      not yet the declared url:

          git -C ${path} remote add fork <fork-url>
          git -C ${path} fetch fork
          git -C ${path} checkout ${pinned}

      If it exists only on someone's machine, it has to be pushed before this
      repository can be cloned by anyone else.
MSG
done < <(git config -f .gitmodules --get-regexp '^submodule\..*\.path$' | awk '{print $2}')

if [ "$missing" -ne 0 ]; then
    echo >&2
    echo "error: one or more submodule pins are unreachable (see above)" >&2
    exit 1
fi

echo "All submodule pins resolved."

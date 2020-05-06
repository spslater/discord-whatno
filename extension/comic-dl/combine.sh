#!/usr/bin/env bash

echo $1
echo $2

cd "$1"

for dir in $(ls -d */); do
	if [[ "$dir" != "." ]]; then
		pushd "$dir"
		name=${dir::-1}
		zip -ur ~/media/reading/comics/"$2/$2.cbz" *.png
		popd
	fi
done

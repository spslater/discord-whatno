#!/usr/bin/env bash

echo $1
echo $2

cd "$1"

for dir in $(find . -type d); do
	if [[ "$dir" != "." ]]; then
		name=${dir:2}
		zip -r ~/media/reading/comics/"$2/$2 - $name.cbz" $dir/*.png
	fi
done

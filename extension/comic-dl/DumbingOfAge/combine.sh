#!/usr/bin/env bash

for dir in "$@"; do
	zip ~/media/reading/comics/"Dumbing of Age/Dumbing of Age - $dir.cbz" $dir/*.png
done

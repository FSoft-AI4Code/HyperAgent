#!/bin/bash

cd 'Defects4J/repos'
orgdir=$(pwd)
for bname in $(find . -mindepth 1 -maxdepth 1 -type d | sort -V); do
	cd ${orgdir}/${bname}
	bname=${bname#*/}

	# setup
	git reset --hard HEAD > /dev/null 2>&1
        git clean -df > /dev/null 2>&1
	git checkout D4J_${bname}_POST_FIX_COMPILABLE > /dev/null 2>&1
	if [[ $? -ne 0 ]]; then
		git checkout D4J_${bname}_POST_FIX_REVISION > /dev/null 2>&1
	fi
        git reset --hard HEAD > /dev/null 2>&1
        git clean -df > /dev/null 2>&1
        for ncfile in $(git diff D4J_${bname}_BUGGY_VERSION --name-only); do
                if [[ ${ncfile} == *"java"* ]]; then
                        continue
                fi
                git checkout D4J_${bname}_BUGGY_VERSION -- ${ncfile} 2> /dev/null
        done

	# bring pre-fix-compilable 
	git checkout D4J_${bname}_PRE_FIX_COMPILABLE -- $(defects4j export -p dir.src.tests 2> /dev/null)
        defects4j compile 2> /dev/null

	# if initially okay, return to loop
	if [[ $? -eq 0 ]]; then
		echo "${bname},ok"
		git commit -m "D4J_${bname}_POST_FIX_PRE_TEST_COMPILABLE"
		git tag D4J_${bname}_POST_FIX_PRE_TEST_COMPILABLE
		cd ${orgdir}
		continue
	fi

	# attempt to fix
# 	if [[ ${bname} == *"Jackson"* ]]; then
#                 for fname in $(git diff D4J_${bname}_BUGGY_VERSION --name-only | grep "PackageVersion"); do
#                         git checkout D4J_${bname}_BUGGY_VERSION -- ${fname}
#                 done
#         fi

	for fname in $(defects4j compile 2>&1 | grep -o "${bname}/.*\.java.*error" | grep -o "${bname}/.*\.java" | sort -u); do
		git rm -f ${fname#*/}
	done
	
	# report fix results
	defects4j compile > /dev/null 2>&1
	if [[ $? -eq 0 ]]; then
		echo "${bname},fixed"
 		git commit -m "D4J_${bname}_POST_FIX_PRE_TEST_COMPILABLE"
                git tag D4J_${bname}_POST_FIX_PRE_TEST_COMPILABLE
	else
		echo "${bname},fail"
	fi

	# restore state
	cd ${orgdir}
done

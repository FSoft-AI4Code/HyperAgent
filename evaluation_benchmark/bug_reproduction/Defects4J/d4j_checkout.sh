cdir=$(pwd)
D4J_HOME="$(dirname $(which defects4j))/../../"

for proj in $(defects4j pids); do
    for bug in $(cut -f1 -d',' "$D4J_HOME/framework/projects/$proj/commit-db"); do
        defects4j checkout -p $proj -v ${bug}b -w Defects4J/repos/${proj}_${bug}
    done
done


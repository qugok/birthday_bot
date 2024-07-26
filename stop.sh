WORK_DIR="/home/diploma/tanya_birthday"
RUN_DIR="$WORK_DIR/run"

mkdir -p $RUN_DIR
mkdir -p $RUN_DIR/pids
mkdir -p $RUN_DIR/logs


function StopApp {
    app_name=$1
    if [ -f $RUN_DIR/pids/$app_name.pid ]; then
        kill `cat $RUN_DIR/pids/$app_name.pid`
    fi
}
function runApp {
        app_name=$1

        StopApp $app_name

        daemon  --name=$app_name \
        --pidfile=$RUN_DIR/pids/$app_name.pid \
        --chdir=$WORK_DIR \
        --unsafe --respawn --attempts=1 --delay=60 \
        --stdout=$RUN_DIR/logs/$app_name.out \
        --stderr=$RUN_DIR/logs/$app_name.err \
        -- python3 $WORK_DIR/main.py
}
# runApp "tanya_birthday"
StopApp "tanya_birthday"

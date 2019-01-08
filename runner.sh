#!/bin/bash

# Run the experiment and collect PIDs
echo "Executing experiment '$3' with seeds from $1 to $2"
for ((i = $1; i <= $2; i++))
do
    echo "Seed: $i"
    OUTPUT_FILE=outputs/$3_$i.output
    (/usr/bin/time -f '%P %M %E %S %U' python ExperimentController.py --seed $i --experiment examples/$3/) &> $OUTPUT_FILE &
    #(gtime -f '%P %M %E %S %U' python ExperimentController.py --seed $i --experiment examples/$3/) &> $OUTPUT_FILE &
    pids[${i}]=$!
    sleep 5
done

# Wait for each PID to complete
for pid in ${pids[*]}; do
  wait $pid
done

# Postprocess
for ((i = $1; i <= $2; i++)); do
  python PostProcess_SEAMS19.py $OUTPUT_FILE $i $3
done

##### If you don't want it running in parallel, comment out the above and use the below cocde
#echo "Executing experiment '$3' with seeds from $1 to $2"
#for ((i = $1; i <= $2; i++))
#do
#    echo "Seed: $i"
#    OUTPUT_FILE=outputs/$3_$i.output
#    (/usr/bin/time -f '%P %M %E %S %U' python ExperimentController.py --seed $i --experiment examples/$3/) &> $OUTPUT_FILE
#done

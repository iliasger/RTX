#!/bin/bash
echo "Executing experiment '$3' with seeds from $1 to $2"
for ((i = $1; i <= $2; i++))
do
    echo "Seed: $i"
    OUTPUT_FILE=outputs/$3_$i.output
    (gtime -f '%P %M %E %S %U' python ExperimentController.py --seed $i --experiment examples/$3/) &> $OUTPUT_FILE
    python PostProcess_SEAMS19.py $OUTPUT_FILE $i $3
done
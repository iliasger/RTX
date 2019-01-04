# Online Appendix 

### Performance measurement
Run your python script as:

`(/usr/bin/time -f '%P %M %E %S %U' python <SCRIPT_TO_EXECUTE>) |& tee <OUTPUT_FILE>.output`

Then, run `python PostProcess_SEAMS19.py <OUTPUT_FILE>.output` to parse the performance metrics and add to the ElasticSearch database created by your most recent run.

On a Mac, first install gnu-time (`brew install gnu-time`), then run the above command with `gtime -f ...`
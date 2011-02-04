#!/bin/bash
# Script: convert_ingest
# Convert eps files to png and ingest xml files to EcoConnect database
ZOPE_URL='http://makaro.niwa.co.nz:8082/products'
ZOPE_LOCATION='/data/images/mintaka-oper/products'
INPUT_DIRECTORY=${QSUB_WORKDIR:-.}
OUTPUT_DIRECTORY=${QSUB_WORKDIR:-.}

# Operational 
#INGEST_URL="http://ecapp1.niwa.co.nz:7777/ecoconnect/services/IngestionWebService"
#INGEST_USERNAME="ForecastIngestion"
#INGEST_PASSWORD="product1on"

# Test
INGEST_URL="http://ecapp1-dev.niwa.co.nz:7777/ecoconnect/services/IngestionWebService"
INGEST_USERNAME="ForecastIngestion"
INGEST_PASSWORD="test1ng"

#set -x
#set -e; trap 'cylc task-failed' ERR

decho='echo'

let "NLISTS = 4"  #Number of parallel processing streams for creating the .PNG files.

# Source common functions
SYSTEM=${USER##*_}
if [ "$HOST" = "pa" ]   #This bit of code should eventually be removed.
then
  CLASS_PATH="/$SYSTEM/ecoconnect_$SYSTEM/bin"
  BIN_PATH="/$SYSTEM/ecoconnect_$SYSTEM/bin"
else
  CLASS_PATH="/$SYSTEM/ecoconnect/ecoconnect_$SYSTEM/bin"
  BIN_PATH="/$SYSTEM/ecoconnect/ecoconnect_$SYSTEM/bin"
fi

. $BIN_PATH/ecfunctions.sh

BASE_DIR=${PRODUCT_DIR:-$PWD}   # Set BASE_DIR either to current or to PRODUCT_DIR if defined.
cd $BASE_DIR                    # cd here anyway just in case PRODUCT_DIR is defined

if [ "$USER" = "tinker" ]
then 
  . /home/tinker/ecoconnect/visualization/shell_scripts/ecfunctions.sh  #For testing
  CLASS_PATH="/home/tinker/ecoconnect/visualization/shell_scripts/bin"
fi

# Pushing data to the operational database
if [ "$SYSTEM" = "oper" ]
then
  echo "This script is running under oper"
  INGEST_URL="http://ecapp1.niwa.co.nz:7777/ecoconnect/services/IngestionWebService"
  INGEST_USERNAME="ForecastIngestion"
  INGEST_PASSWORD="product1on"
fi

ingest="java -cp $CLASS_PATH/axis.jar:$CLASS_PATH/commons-discovery-0.2.jar:$CLASS_PATH/wss4j-1.5.0.jar:$CLASS_PATH/commons-logging.jar:$CLASS_PATH/jaxrpc.jar:$CLASS_PATH/jsr173_1.0_api.jar:$CLASS_PATH/log4j.jar:$CLASS_PATH/saaj.jar:$CLASS_PATH/wsdl4j-1.5.1.jar:$CLASS_PATH/xbean.jar:$CLASS_PATH/MintakaIngestion_Client.jar:$CLASS_PATH/MintakaIngestion.jar:$CLASS_PATH/xmlsec-1.4.0.jar uk.gov.ecoconnect.ingestion.Main $INGEST_USERNAME $INGEST_PASSWORD -file"

ingest_mult="java -cp $CLASS_PATH/axis.jar:$CLASS_PATH/commons-discovery-0.2.jar:$CLASS_PATH/wss4j-1.5.0.jar:$CLASS_PATH/commons-logging.jar:$CLASS_PATH/jaxrpc.jar:$CLASS_PATH/jsr173_1.0_api.jar:$CLASS_PATH/log4j.jar:$CLASS_PATH/saaj.jar:$CLASS_PATH/wsdl4j-1.5.1.jar:$CLASS_PATH/xbean.jar:$CLASS_PATH/MintakaIngestion_Client.jar:$CLASS_PATH/MintakaIngestion.jar:$CLASS_PATH/xmlsec-1.4.0.jar uk.gov.ecoconnect.ingestion.Main $INGEST_USERNAME $INGEST_PASSWORD @file"

REFERENCE_TIME=${1:-$CYCLE_TIME}
if [ ! -n "$REFERENCE_TIME" ]
then

  MSG="no CYCLE_TIME specified for $USER"
  cylc task-message $MSG
  cylc task-failed
  $NAGIOS $SERVICE CRITICAL "$MSG"
  exit 1
fi

# =======================================
# Functions

#lowercase_filename()
# Routine to select any .gif/.GIF files and convert all the characters
# in the file name to lowercase.
lowercase_filename()
{
  for file in *
  do
    if [[ $file =~ "\*" ]]; then continue; fi  #Ignore "*xxxx" if there are no.GIF files for example
    file_lower=`echo $file | tr A-Z a-z`
    case $file_lower in
    *.gif | *.png)
      if [ ! -e "$file_lower" ];then  mv $file $file_lower; fi
        ;;
    esac
  done
}

f_locdate()
# Routine to return the position in the string of the analysis  (ie the 1st set of characters
# that consist of 8 digits)
# If no string of 8 digits are found, a value of -1 (255) is returned.
{
len_str=${#1}
if [ -z "$2" ]; then nchars=8; else nchars=$2; fi
if [ $len_str -lt $nchars ]; then return -1; fi

for (( i=0; i<=$len_str-$nchars; i++ ))
do
 tmp=${1:$i:$nchars}
# tlen=`expr "$tmp" : '[0-9]\{8\}'`
 tlen=`expr "$tmp" : "[0-9]\{$nchars\}"`
 if [ $tlen -eq $nchars ]; then return $i; fi
done
  return -1
}

#mv_sat_files()
# Routine to move .gif files into the appropriate directory for processing
mv_sat_files()
{
  for file in *$REF_TIME*.gif 
  do
    file_root=${file%%.*}
    if $debug; then $decho convert $file $file_root.png; fi
    if ! $debug; then convert $file $file_root.png; fi
    if $debug; then $decho mv $file $ARCHIVE_DIR/; fi
    if ! $debug; then mv $file $ARCHIVE_DIR/; fi
  done

  for file in {*$REF_TIME*.gif,*$REF_TIME*.png}
  do
    if [[ $file =~ "\*" ]]; then continue; fi
    field1=${file%%_*}
    field1=${field1#*-}
    field2=`expr "$file" : '[a-z0-9-]*_\([a-z0-9]*\)'`
    if [ ! -d "$field1/product/areal/$REF_TIME" ]; then mkdir -p $field1/product/areal/$REF_TIME/ ; fi
    mv $file $field1/product/areal/$REF_TIME/
  done
}

#
# create_sat_xml()
# Routine to create a set of .xml files from the set of .png files that
# exist in the current directory that have the appropriate analyses time
create_sat_xml()
{
local found="false"
let "grouplast = 0"    #Used in classifying the products etc.
local ref_year=${REF_TIME:0:4}
local ref_mth=${REF_TIME:4:2}
local ref_day=${REF_TIME:6:2}
local ref_hour=${REF_TIME:8:2}
local ref_min=${REF_TIME:10:2}

for file in {m-*_${REF_TIME}*.gif,m-*_${REF_TIME}*.png}   #Only want to do this with m-* type files.
do
  if [[ $file =~ "\*" ]]; then continue; fi  #remove any m-* values should there only be .png files and no gif files eg
  file_root=${file%*.*}
  file_root=${file_root##m-}  #Remove m-
  product=`expr $file_root : '\([a-z0-9\+\-]*\)'`  #Get the next field after the - (eg ir11)
  field1=${field1#*-}
  field2=`expr "$file" : '[a-z0-9\-]*_\([a-z0-9-]*\)'`
  field3=`expr "$file" : '[a-z0-9\-]*_[a-z0-9\-]*_\([a-z0-9-]*\)'`
  field3=`echo $field3 | tr a-z A-Z`               #Want this in Uppercase.
  field4=`expr "$file" : '[a-z0-9\-]*_[a-z0-9\-]*_[a-z0-9\-]*_\([a-z0-9-]*\)'`
  
  xml_file="$file_root.xml"
  echo '<?xml version="1.0" encoding="UTF-8"?>' > $xml_file
  echo "<observationImages xmlns='http://datatypes.ingestion.ecoconnect.gov.uk'" >> $xml_file
  echo "             name=\""$product: $field4\"">" >> $xml_file
  echo "   <observationImageSet>" >> $xml_file
  echo "     <imageData validityTime=\"$ref_year-$ref_mth-$ref_day""T$ref_hour:$ref_min:00.0Z\"" >> $xml_file
  echo "         fileName=\"$file\" source=\"$field3\"/>" >> $xml_file
  echo "   </observationImageSet>" >> $xml_file
  echo "</observationImages>" >> $xml_file

done 
}

# create_cliex_xml()
# Routine to create xml files for the Climate_Explorer png files.
# This xml routine is a bit more tricky because the fields cannot be
# directly determined from the filenames.  There are mapping files
# in $HOME/control/climate_explorer, eg., which hold the mappings
#
# Required environmental variables:
# CONTROL_DIR   - Directory that contain the control files
#
create_cliex_xml()
{
  if [ -z "$CONTROL_DIR" ]
  then
    MSG="No Control Directory has been specified for create_cliex_xml()"
    $LOGGER -i -p $FACILITY.info -t $PROG_NAME $MSG
    exit 1
  fi

  
  for file in *.png
  do
  if [[ $file =~ "\*" ]]; then continue; fi  #If no files, will return *.png - this would cause an ouch
 
  file_root=${file%*.*} 
  f_locdate $file    #Extract the date out of the file name.
  pos=$?
  if [ $pos -eq 255 ]; then continue; fi   #Must have a conforming date string in the name 
  ref_year=${file:$pos:4}
  ref_mth=${file:$pos+4:2}
  ref_day=${file:$pos+6:2}
  ref_hour="09"
  ref_min="00"
  ref_datetime="$ref_year$ref_mth$ref_day $ref_hour:$ref_min"
  ref_dattime_utc=`date --date "$ref_datetime 12 hours ago" "+%Y%m%d%H%M"`
  validity_Time="${ref_dattime_utc:0:4}-${ref_dattime_utc:4:2}-${ref_dattime_utc:6:2}T${ref_dattime_utc:8:2}:${ref_dattime_utc:10:2}:00.0Z"
  prefix=${file:0:$pos}
  prefix_string="^"$prefix","
  csv_line=`grep -h -P "$prefix_string" $CONTROL_DIR/*.csv`
  result=$?
  if [ ! $result -eq 0 ]; then continue; fi    #Prefix not found in any csv file.
  csv_file=`grep -H -P "$prefix_string" $CONTROL_DIR/*.csv`
  csv_file=${csv_file##*\/}       #Get rid of preceding path
  csv_file=${csv_file%%\.*}       #Everything to the left of .csv
  result=$?
  if [ ! $result -eq 0 ]; then continue; fi    #Prefix not found in any csv file.
  
  csv_line=${csv_line#*,}	#Get rid of everything up to the ","
#  csv_line=`expr "$csv_line" : '[[:space:]]*\([[:print:]]*\)'`  #Remove leading spaces if any
#  csv_line=`expr "$csv_line" : '\([[:print:]]*[[:alnum:]]\)'`   #Remove any trailing spaces, if any
  csv_line=`echo "$csv_line" | sed 's/^[ \t]*//;s/[ \t]*$//'`   #Removes leadingi & trailing spaces &tabs (faster than the above two lines)
  csv_type=${csv_file%%_*}      #Eg NCEP or CliEx
  csv_type=`echo $csv_type | tr a-z A-Z`    #NCEP or CLIEX

  NCEP="false"
####   if [ $csv_type = "NCEP" ]; then NCEP="true"; fi     #Decision made to make everything observational

#  echo $ref_datetime  :  $ref_dattime_utc  : $validity_Time  : $csv_line

  xml_file="$file_root.xml"
  if $NCEP
  then
    echo '<?xml version="1.0" encoding="UTF-8"?>' > $xml_file
    echo "<areaForecast xmlns='http://datatypes.ingestion.ecoconnect.gov.uk'" >> $xml_file
    echo "             name=\""$csv_line\""" >> $xml_file
    echo "             analysisTime=\"$validity_Time\">" >> $xml_file
    echo "   <areaForecastImageSet>" >> $xml_file
    echo "     <imageData validityTime=\"$validity_Time\"" >> $xml_file
    echo "         fileName=\"$file\"/>" >> $xml_file
    echo "   </areaForecastImageSet>" >> $xml_file
    echo "</areaForecast>" >> $xml_file
  else
    echo '<?xml version="1.0" encoding="UTF-8"?>' > $xml_file
    echo "<observationImages xmlns='http://datatypes.ingestion.ecoconnect.gov.uk'" >> $xml_file
    echo "             name=\""$csv_line\"">" >> $xml_file
    echo "   <observationImageSet>" >> $xml_file
    echo "     <imageData validityTime=\"$validity_Time\"" >> $xml_file
    echo "         fileName=\"$file\" source=\"Climate\"/>" >> $xml_file
    echo "   </observationImageSet>" >> $xml_file
    echo "</observationImages>" >> $xml_file
  fi
  done
}
#
# Create_png()
# Routine to create .png files from .eps files in the current directory that 
# have the specified reference time.
# syntax: create_png m-||""   
#   m- is used for the Mintaka files, 
#   null argument when dealing with old-style stage0 files.
create_png()
{

# Make sure that there is a ./done/ directory
if [ ! -e done/ ]; then
  mkdir done/
fi

#
prexf="$1"
let count=0

for file in *_${REF_TIME}*.eps
do
  field2=`expr "$file" : '[a-z0-9-]*_\([a-z0-9]*\)'`        #Yep, it's true - returns y from x_y_z!
  if [ "$field2" != "$REF_TIME" ]; then continue; fi        #Avoid hitting on a validity time rather than reference time
    case $file in
    m-*)               # Only convert files that are Mintaka files if m- is specified
      if [ "$prexf" != "m-" ]; then continue; fi
      ;;
    *)                 # Else, only convert files that don't start with m- is m- isn't specified.
      if [ "$prexf" = "m-" ]; then continue; fi
        ;;
  esac
  let count+=1
  flist[$count]=$file 
done

# Now have a list of files, split these up into NLIST groups and convert them in parallel.

let MaxCount=$count
for (( loop_count=1; loop_count<=$NLISTS; loop_count++ ))
do
  for (( counter=${loop_count}; counter<=$MaxCount; counter+=$NLISTS ))
  do
    file=${flist[$counter]}
    outfile=$OUTPUT_DIRECTORY/${file/.eps}  #Remove .eps
    image_file=$outfile.png

    if $debug; then echo loop_count=$loop_count   counter=$counter; fi

    case $file in
    *nz1* )
#      if $debug1 ; then $decho convert -density 120x120 -resize x632 -depth 8 $file $outfile.png; fi
#      if ! $debug ;  then convert -density 120x120 -resize x632 -depth 8 $file $outfile.png; fi
      if $debug1 ; then $decho convert -density 120x120 -resize x632 -quality 90 -depth 8 -colors 256 $file $outfile.png; fi
      if ! $debug ;  then convert -density 120x120 -resize x632 -quality 90 -depth 8 -colors 256 $file $outfile.png; fi
      result=$?
       ;;
    *nni* | *ssi* | *cnz*)
#      if $debug1 ; then $decho convert -density 120x120 -resize x512 -depth 8 $file $outfile.png; fi
#      if ! $debug ;  then convert -density 120x120 -resize x512 -depth 8 $file $outfile.png; fi
      if $debug1 ; then $decho convert -density 120x120 -resize x512 -quality 90 -depth 8 -colors 256 $file $outfile.png; fi
      if ! $debug ;  then convert -density 120x120 -resize x512 -quality 90 -depth 8 -colors 256 $file $outfile.png; fi
      result=$?
       ;;
    *-ni-* | *-si-* | *-cen-* | *po1*)
#      if $debug1 ; then $decho convert -density 120x120 -resize x528 -depth 8 $file $outfile.png; fi
#      if ! $debug ;  then convert -density 120x120 -resize x528 -depth 8 $file $outfile.png; fi
      if $debug1 ; then $decho convert -density 120x120 -resize x528 -quality 90 -depth 8 -colors 256 $file $outfile.png; fi
      if ! $debug ;  then convert -density 120x120 -resize x528 -quality 90 -depth 8 -colors 256 $file $outfile.png; fi
      result=$?
       ;;
    met0* | met1*)
#      if $debug1 ; then $decho convert -density 120x120 -resize x440 -depth 8 $file $outfile.png; fi
#      if ! $debug ; then convert -density 120x120 -resize x440 -depth 8 $file $outfile.png; fi
      if $debug1 ; then $decho convert -density 120x120 -resize x440 -quality 90 -depth 8 -colors 256 $file $outfile.png; fi
      if ! $debug ; then convert -density 120x120 -resize x440 -quality 90 -depth 8 -colors 256 $file $outfile.png; fi
      result=$?
        ;;
    *gwave*)
#      if $debug1 ; then $decho convert -density 120x120 -resize x544 -depth 8 $file $outfile.png; fi
#      if ! $debug ; then convert -density 120x120 -resize x544 -depth 8 $file $outfile.png; fi
      if $debug1 ; then $decho convert -density 120x120 -resize x544 -quality 90 -depth 8 -colors 256 $file $outfile.png; fi
      if ! $debug ; then convert -density 120x120 -resize x544 -quality 90 -depth 8 -colors 256 $file $outfile.png; fi
      result=$?
        ;;
      *)
#        if $debug1 ; then $decho convert -density 120x120 -resize x608 -depth 8 $file $outfile.png; fi
#        if ! $debug ; then convert -density 120x120 -resize x608 -depth 8 $file $outfile.png; fi
        if $debug1 ; then $decho convert -density 120x120 -resize x608 -quality 90 -depth 8 -colors 256 $file $outfile.png; fi
        if ! $debug ; then convert -density 120x120 -resize x608 -quality 90 -depth 8 -colors 256 $file $outfile.png; fi
        result=$?
        ;;
    esac

    if [ ! $result -eq 0 ]
    then
      MSG="Convert for file $file failed"
      cylc task-message $MSG
    fi 

# Store the eps file in done/ directory
    if $debug ; then $decho mv $file done/ ; fi
    if ! $debug ;  then mv $file done/ ; fi

  done &

done
wait
}

#
# create_xml()
# Routine to create a set of .xml files from the set of .png files that
# exist in the current directory that have the appropriate analyses time
create_xml()
{
local found="false"
local grouplast
local ref_year=${REF_TIME:0:4}
local ref_mth=${REF_TIME:4:2}
local ref_day=${REF_TIME:6:2}
local ref_hour=${REF_TIME:8:2}

let "grouplast = 0"    #Used in classifying the products etc.

for file in m-*_${REF_TIME}*.png   #Only want to do this with m-* type files.
do
  field2=`expr "$file" : '[a-z0-9-]*_\([a-z0-9]*\)'`
  if [ "$field2" != "$REF_TIME" ]; then continue; fi #Avoid any leftover png files with a validity time=reference_time
# form an array of unique identities based on model, product and area.
   file_root=${file%*.*}    #Remove .png
   file_root=${file_root##m-}  #Remove m-
#   echo root file = $file_root

   product=`expr $file_root : '\([a-z0-9\+\-]*\)'`  #Get the next field after the - (eg rrf)
#   echo product = $product

   model=`expr $file_root : '[a-z0-9\+\-]*_[a-z0-9\+\-]*_[a-z0-9\+\-]*_[a-z0-9\+\-]*_\([a-z0-9\+\-]*\)'`
   model_area=`expr $file_root : '[a-z0-9\+\-]*_[a-z0-9\+\-]*_[a-z0-9\+\-]*_[a-z0-9\+\-]*_[a-z0-9\+\-]*_\([a-z0-9\+\-]*\)'`

#  echo model area = $model_area
# Now need to sort into unique groups
   value="$model $product $model_area"
   found="false"
   for (( group=1; group<=grouplast; group++ ))
   do
     if [ "${unique_list[$group]}" == "$value" ]
     then
       found="true"
     fi
   done
# Already indexed?
   if ! $found
   then
     let grouplast+=1
     unique_list[$grouplast]="$value"
     found="false"
   fi
done

# Now we have the list of unique groups,
# go through them and create the xml file headers and populate them.
for (( group=1; group<=grouplast; group++ ))
do
  line=${unique_list[$group]}
  model=`expr "$line" : '\([a-z0-9\+\-]*\)'`
  MODEL=`echo $model | tr a-z A-Z`   #Uppercase version
  prod=`expr "$line" : '[a-z0-9\+\-]*[[:space:]]\([a-z0-9\+\-]*\)'`
  area=`expr "$line" : '[a-z0-9\+\-]*[[:space:]][a-z0-9\+\-]*[[:space:]]\([a-z0-9\+\-]*\)'`
  xml_file=${prod}_${REF_TIME}'_'${model}_${area}.xml
#
# Create the xml header for this set of files.
     echo '<?xml version="1.0" encoding="UTF-8"?>' > $xml_file
     echo "<areaForecast xmlns='http://datatypes.ingestion.ecoconnect.gov.uk'" >> $xml_file
     echo "               name=\"$MODEL $prod: $area V1.0\"" >> $xml_file
     echo "               analysisTime=\"$ref_year-$ref_mth-$ref_day""T$ref_hour:00:00.0Z\">" >> $xml_file
     echo "  <areaForecastImageSet>" >> $xml_file

    file_in=${prod}_${REF_TIME}'_*'${model}_${area}'*'.png
#
#Now populate the xml file
    for file in "m-"$file_in
    do
      validity_time=`expr "$file" : '[a-z0-9\+\-]*_[a-z0-9\+\-]*_\([a-z0-9\+\-]*\)'`
      val_year=${validity_time:0:4}
      val_mth=${validity_time:4:2}
      val_day=${validity_time:6:2}
      val_hour=${validity_time:8:2}
      period=`expr "$file" : '[a-z0-9\+\-]*_[a-z0-9\+\-]*_[a-z0-9\+\-]*_\([a-z0-9\+\-]*\)'`

     echo "    <imageData validityTime=\"$val_year-$val_mth-$val_day""T$val_hour:00:00.0Z\"  fileName=\"$file\"/>" >>$xml_file

    done
#   Close the xml file
  echo "  </areaForecastImageSet>" >> $xml_file
  echo "</areaForecast>" >> $xml_file
done
}

# ingest_xml_mult() [archive path]
# Ingestion function to upload the data. This routine uses the version of the 
# ingestion program that uses a file to specify the list of xml files to ingest
# and the number of files to ingest in one session.
#
# Unfortunately, the ingest java program insists on archiving the .png or .gif files
# if such are specified in the xml file.  We do not always want to do this - sometimes
# these files will be wanted again later.
#
# To get around this problem, the environmental variable ARCHIVE_LOC is used to specify
# the location to archive to.  This can be set to a temporary location by specifying it 
# as the [1st] parameter: eg
#
#  syntax: ingest_xml_mult
#      or: ingest_xml_mult ./archive   (for example)
#
# We also have the problem that we wish to archive "data" xml files, but not the metadata xml files.
# To do this, the option "-archive" can be passed as the 1st or 2nd parameter
#
#  syntax: ingest_xml_mult '-archive'            #(Make sure it is exact) or
#          ingest_xml_mult ./archive '-archive'  #to specify both the archive directory and 
#                                                #force the archiving of the xml files.
#
# If the archive directory isn't specified as the parameter, if will default to ARCHIVE_DIR
#
ingest_xml_mult()
{
# 1st collect a list of files to process
local Pid="$$"
local XML_FILE_LIST="xml_file_list_$Pid.lis"
local TRANCHE="3"    #Number of files from the list to ingest at once.
local ARCHIVE_LOC=$ARCHIVE_DIR
local Routine="ingest_xml_mult"
local ARCHIVE_XML="false"      #Default setting
local result

# Check to see if xml files are to be archived and set the flag appropriately

if [[ "$1" = '-archive' || "$2" = '-archive' ]]
then
  ARCHIVE_XML="true"
fi

if [ ! "$1" = '-archive' ]
then
  ARCHIVE_LOC=${1:-"$ARCHIVE_DIR"}
fi

result=0
if [[ ! -d $ARCHIVE_LOC && "$ARCHIVE_XML" == "true" ]]  #Check to see if archive directory exists and create it if necessary
then 
  MSG="${Routine}: $ARCHIVE_LOC not found, creating directory"
  cylc task-message $MSG
  mkdir $ARCHIVE_LOC/ 

  result=$?
  if [ ! $result -eq 0 ]
  then
    MSG="${Routine}: Unable to create archive directory $ARCHIVE_LOC"
    cylc task-message $MSG
  else
    chmod g+rw $ARCHIVE_LOC
    result=$?
    if [ ! $result -eq 0 ]
    then
      MSG="${Routine}: Unable to chmod g+rw for $ARCHIVE_LOC after creating it"
      cylc task-message $MSG
    fi
  fi
fi #Make sure that the directory exists

if [ ! -d ./done ]; then mkdir ./done/; fi             #Make sure that there is a done directory
result=$?
if [ ! $result -eq 0 ]
then
  MSG="${Routine}: Unable to create directory $PWD/done"
  cylc task-message $MSG
fi

if [ ! -d ./failed ]; then mkdir ./failed/; fi         #Make sure that there is a failed directory
result=$?
if [ ! $result -eq 0 ]
then
  MSG="${Routine}: Unable to create directory $PWD/failed"
  cylc task-message $MSG
fi

let total_count=0
if [ -f "$XML_FILE_LIST" ]; then rm -f $XML_FILE_LIST; fi
for xml_file in *.xml
do
  if [ ! -e "$xml_file" ]; then continue; fi #ie, possibly no files to process.
  if [ ! -f "$xml_file.lok" ]                # Account for possibility that two processes are trying to work here at once.
  then                                       # Does a lock file exist? If not
    lockfile -1 -r 1 $xml_file.lok           # then try and create a lock file
    result=$?                                # Success?
    if [ $result = 0 ]                       # If yes, then add this entry to the list of files to process
    then                                     # otherwise ignore.  Presume that the other process has captured this file.
      let total_count+=1
      echo $xml_file >> $XML_FILE_LIST
    fi
  fi
done
#OK now have a list of files to process, start the ingestion program going to ingest them.
if [ -f $XML_FILE_LIST ]; then $ingest_mult $XML_FILE_LIST $INGEST_URL $TRANCHE './done/' './failed/' $ARCHIVE_LOC ; fi
result=$?

if [ $result -eq 18 ]    #A return code of 18 will result if ARCHIVE_LOC cannot be written to.
then
  MSG="${Routine}: ingest_mult error code 18 - Java ingestion routine cannot write to $ARCHIVE_LOC"
  cylc task-message -p CRITICAL "$MSG"
  cylc task-failed
  exit 1
  if $debug; then $decho $NAGIOS $SERVICE CRITICAL "ingest_mult cannot write to $ARCHIVE_LOC"; fi
  if ! $debug; then $NAGIOS $SERVICE CRITICAL "ingest_mult cannot write to $ARCHIVE_LOC"; fi
fi

# Now need to check to see how many of these failed....

if [ -f $XML_FILE_LIST ]  #It may be that there was nothing to do, in which case enjoy and do nothing.
then
  let fail_count=0
  while read line
  do
    if [ -f "./failed/$line" ]
    then 
      let fail_count+=1; 
      MSG="${Routine}: Failed to ingest xml file $PWD/$line"
      cylc task-message $MSG
    fi   #Count all the files in ./failed that are listed in the listing file.
    rm -f $line.lok          #Remove lock file.
  done < $XML_FILE_LIST

# Issue a NAGIOS alert or warning.
  if [ ! "$fail_count" -eq 0 ]
  then
    MSG="${Routine}: Failed to ingest $fail_count of $total_count files"
    cylc task-message $MSG

    if [ "$fail_count" -eq "$total_count" ]	#A major problem
    then
      NAGIOS_STATUS="CRITICAL"
       case "${USER%%_*}"  in
        sat)       #Don't want to report ingest failure as critical for sat uploads.
             if $debug; then $decho $NAGIOS $SERVICE WARNING "Failed to ingest $fail_count of $total_count xml files $BASE_DIR"; fi
             if ! $debug; then $NAGIOS $SERVICE WARNING "Failed to ingest $fail_count of $total_count xml files $BASE_DIR"; fi
           ;;
          *)
             if $debug; then $decho $NAGIOS $SERVICE CRITICAL "Failed to ingest $fail_count of $total_count xml files for $BASE_DIR"; fi
             if ! $debug; then $NAGIOS $SERVICE CRITICAL "Failed to ingest $fail_count of $total_count xml files for $BASE_DIR"; fi
             cylc task-message -p CRITICAL "Failed to ingest $fail_count of $total_count xml files for $BASE_DIR"
            ;;
        esac
    else
      if [ ! "$NAGIOS_STATUS" = "CRITICAL" ]   #Only issue a WARNING if status is not already critical
      then
        if $debug; then $decho $NAGIOS $SERVICE WARNING "Failed to ingest $fail_count of $total_count xml files $BASE_DIR"; fi
        if ! $debug; then $NAGIOS $SERVICE WARNING "Failed to ingest $fail_count of $total_count xml files $BASE_DIR"; fi
      fi
    fi
  fi

# If we 1st wish to archive the xml files, then loop through the contents of XML_FILE_LIST and "cp -p" the files to the
# archive directory defined by ARCHIVE_LOC

  if [ "$ARCHIVE_XML" = "true" ]
  then
    while read line
    do
      if [ -f "./done/$line" ]
      then
        cp -p "./done/$line" $ARCHIVE_LOC
      fi
    done < $XML_FILE_LIST
  fi

# Temporarily store the list file.
  mv $XML_FILE_LIST ./done/
  NAGIOS="echo NAGIOS"
fi
}

# archive_images()
# Routine to move the files that have been successfully uploaded to Mintaka into 
# the archive directory
archive_images()
{
  local Routine="archive_images"
  local result
  local result_mv
  local file_class=$1
#
# Check to see that the archive directory exists
#
  if [ ! -d $ARCHIVE_DIR ]
  then 
    MSG="${Routine}: ARCHIVE_DIR $ARCHIVE_DIR not found"
    cylc task-message $MSG
    exit
  fi

  for file in {*$REF_TIME*.gif,*$REF_TIME*.png}
  do
    if [[ $file =~ "\*" ]]; then continue; fi  #Messy if there are only .gif or .png files (end up with *.png, eg)
    case $file in
    m-*)
      if [ ! "$file_class" = "m-" ]; then continue; fi  #m-* file, but not doing m- files, skip
       ;;
    *)
      if [ "$file_class" = "m-" ]; then continue; fi    #not an m-* file, but doing m- files, skip
       ;;
    esac

    field2=`expr "$file" : '[a-z0-9-]*_\([a-z0-9]*\)'`
    if [ "$field2" != "$REF_TIME" ]; then continue; fi
 
    result=0
    case $file in
    m-*)                       #If Mintaka files, then only archive if xml file successfully uploaded
      grep -sq "$file" done/*${REF_TIME}*.xml
      result=$?
        ;;
    *)                        #Otherwise, archive the .png/gif file regardless.
        ;;
    esac

      result_mv=0   #Check to see if any of the mv operations failed
      if [ $result -eq 0 ] 
      then 
        if $debug; then echo mv $file $ARCHIVE_DIR/; fi
        if $debug1; then echo mv $file $ARCHIVE_DIR/; fi
        if ! $debug; then mv $file $ARCHIVE_DIR/; fi
        result=$?
        if [ $result -ne 0 ]; then result_mv=$result; fi
      fi

    if [ ! ${result_mv} -eq 0 ]
    then
      MSG="${Routine}: Unable to archive some or all files from $PWD"
      if $debug; then echo $LOGGER -i -p $FACILITY.info -t $PROG_NAME $MSG; fi
      if ! $debug; then $LOGGER -i -p $FACILITY.info -t $PROG_NAME $MSG; fi
      cylc task-message $MSG
    fi
  done
}

# cleanup()
# Routine to clean out the ./done directory of files older than n days
#
cleanup()
{
cd done/
if
 $debug
then
  $decho find . -maxdepth 1 -name "*.eps" -ctime +5  -exec rm {} \;
  $decho find . -maxdepth 1 -name "*.xml" -ctime +5  -exec rm {} \;
  $decho find . -maxdepth 1 -name "*.lis" -ctime +5  -exec rm {} \;
else
  find . -maxdepth 1 -name "*.eps" -ctime +5 -exec rm {} \;
  find . -maxdepth 1 -name "*.xml" -ctime +5 -exec rm {} \;
  find . -maxdepth 1 -name "*.lis" -ctime +5 -exec rm {} \;
fi
}

#data_cleanup()
# Routine to clean up the xml files from the ./done and ./failed directories 
# contained in the current directory and move them into ./done and ./failed 
# directories defined by $1
data_cleanup()
{
local Routine="data_cleanup"
if [ -z $1 ]
then
  MSG="${Routine}: - no archival directory supplied as an argument"
  cylc task-message $MSG
  exit
fi
ArchiveRoot=$1   #This is where the archival done/ and failed/ directories will be
  NAGIOS="echo NAGIOS"
if [ ! -d "$ArchiveRoot" ]; then mkdir $ArchiveRoot; fi
if [ ! -d "$ArchiveRoot/done" ]; then mkdir $ArchiveRoot/done/; fi
if [ ! -d "$ArchiveRoot/failed" ]; then mkdir $ArchiveRoot/failed/; fi

# Archive the done files
if [ -d "done/" ]
then
  cd done/
  find . -name "*.xml*" -exec mv {} "$ArchiveRoot/done/" \;
  find . -name "*.lis*" -exec mv {} "$ArchiveRoot/done/" \;
  cd ..
  rm_dir done/
fi

#Archive failed files
if [ -d "failed/" ]
then
  cd failed/
  find . -name "*.xml*" -exec mv {} "$ArchiveRoot/failed/" \;
  find . -name "*.lis*" -exec mv {} "$ArchiveRoot/failed/" \;
  cd ..
  rm_dir failed/
fi
# Remove old stuff from the archive directory
cd "$ArchiveRoot/done/"
find . -maxdepth 1 -ctime +10 -exec rm {} \;
cd "$ArchiveRoot/failed/"
find . -maxdepth 1 -ctime +10 -exec rm {} \;

}
#rm_dir()
# Routine to remove a directory and it's subdirectories - 
# and report failure to logger if not successful
# Directory to be removed must be specified as parameter 1
# Parameter 2 can be a switch associated with rmdir (eg -p)
rm_dir()
{
local Routine="rm_dir"
local dir
if [ -z $1 ]
then
  MSG="${Routine}: - no directory supplied as an argument for removal"
  if $debug; then echo $LOGGER -i -p $FACILITY.info -t $PROG_NAME $MSG; fi
  if ! $debug; then $LOGGER -i -p $FACILITY.info -t $PROG_NAME $MSG; fi
  cylc task-message $MSG
  exit
fi
dir=$1
rmdir_switch=$2

rmdir $rmdir_switch $dir/
result=$?
if [ ! $result -eq 0 ]
then
  MSG="${Routine}: Unable to remove $dir directory from $PWD"
  if $debug; then echo $LOGGER -i -p $FACILITY.info -t $PROG_NAME $MSG; fi
  if ! $debug; then $LOGGER -i -p $FACILITY.info -t $PROG_NAME $MSG; fi
  cylc task-message $MSG
  fi
}

#==========================================================================
# main()     #Just something to search for!
# Script really starts here

echo start script  `date`
REF_TIME="$REFERENCE_TIME"
debug="false"
debug1="false"

if [ ! "$SYSTEM" = "oper" ]
then
  LOGGER="echo $LOGGER"
  NAGIOS="echo $NAGIOS"
fi

# The action that is to take place will depend on the user.
# Currently, the conditions are:
#    sat
#    data
#        climate_explorer
#    <other>


case "${USER%%_*}"  in
  sat)                   #Satellite processing
#  Check that the directory is correct
  if [[ ! "$PWD" = "$HOME/running" ]]
  then
    MSG="call to process sat images, but directory incorrectly set to $PWD"
    if $debug; then echo $LOGGER -i -p $FACILITY.info -t $PROG_NAME $MSG; fi
    if ! $debug; then $LOGGER -i -p $FACILITY.info -t $PROG_NAME $MSG; fi
    exit
  fi

  lowercase_filename
  mv_sat_files

  MSG="Starting create_images for Satellite_Data $REFERENCE_TIME in $BASE_DIR"
  if $debug; then echo $LOGGER -i -p $FACILITY.info -t $PROG_NAME $MSG; fi
  if ! $debug; then $LOGGER -i -p $FACILITY.info -t $PROG_NAME $MSG; fi

  for proc_dir in *
  do 
  if [ ! -d $proc_dir ]; then continue; fi
    if [ -d "$proc_dir/product/areal/$REF_TIME"  ]  #Possibly not all directories will have products for this time
    then 
      cd $proc_dir/product/areal/$REF_TIME
        create_sat_xml
        ingest_xml_mult
        archive_images m-
#        sat_cleanup
        arc_dir=`dirname $PWD`
        data_cleanup $arc_dir
        cd $BASE_DIR
        rm_dir $proc_dir/product/areal/$REF_TIME
    fi
  done
  MSG="create_images completed for Satellite_Data $REFERENCE_TIME in $BASE_DIR"
  $LOGGER -i -p $FACILITY.info -t $PROG_NAME $MSG

exit
       ;;
  data)                       #If the user is data_$SYSTEM, then we need to know what
    case "$BASE_DIR" in          #Expect to be inside the product directory specified by date, eg 
    *climate_explorer*)          #/oper/data_oper/running/climate_explorer/20080520/product
       if [ ! "$SYSTEM" = "oper" ]
       then
         ARCHIVE_DIR="$HOME/running/climate_explorer/archive"
       fi

       REF_TIME=$REFERENCE_TIME  #Not actually used, except for reporting purposes.
       CONTROL_DIR=$HOME/control/climate_explorer

       MSG="Starting create_images for Climate_Explorer $REFERENCE_TIME in $BASE_DIR"
       if $debug; then echo $LOGGER -i -p $FACILITY.info -t $PROG_NAME $MSG; fi
       if ! $debug; then $LOGGER -i -p $FACILITY.info -t $PROG_NAME $MSG; fi

       cd ../
       dated_dir=`basename $PWD`  #Directory we are working under - should be same as $1 or $REFERENCE_TIME
       arc_dir=`dirname $PWD`     #Path to the area to archive xml files etc from done/ and failed/
       cd $BASE_DIR
       cd areal
       create_cliex_xml
       ingest_xml_mult
       data_cleanup $arc_dir

       cd $BASE_DIR/site_specific
       create_cliex_xml
       ingest_xml_mult
       data_cleanup $arc_dir 
       cd $BASE_DIR
       cd ../../   #Make sure we are out of the directory before deleteing it.
       rm_dir $dated_dir/product/areal
       rm_dir $dated_dir/product/site_specific
       rm_dir $dated_dir/product -p
       MSG="create_images completed for Climate_Explorer $REFERENCE_TIME in $BASE_DIR"
       $LOGGER -i -p $FACILITY.info -t $PROG_NAME $MSG
       
     exit
            ;;
     *)
       #placeholder
       exit
            ;;
    esac
       ;;

  *)
# Do the Mintaka process next.
  NAGIOS_STATUS="OK"
  debug="false"
  debug1="false"
  if $debug; then echo $NAGIOS $SERVICE OK "Success"; fi    #Reset the Nagios status
  if ! $debug; then $NAGIOS $SERVICE OK "Success"; fi

cd $BASE_DIR    # cd here in case PRODUCT_DIR has been set as an environmental variable.

# START MESSAGE
  cylc task-started

# Do the areal files for mintaka (m- files) only.
   if [ -d ${BASE_DIR}/areal ]      #Check 1st that there is an "areal" directory
   then
     cd $BASE_DIR/areal
     MSG="Starting png file creation for $REFERENCE_TIME in $PWD"
     cylc task-message $MSG

     create_png m-
     create_xml
     MSG="Completed png file creation for $REFERENCE_TIME in $PWD"
     cylc task-message $MSG

     MSG="Starting ingestion process for $REFERENCE_TIME in $PWD"
     cylc task-message $MSG
#     ingest_xml_mult ./archive    #Ingest, but don't actually archive the png files, yet.
     ingest_xml_mult ./done              #Argument only needed for old zope system

     MSG="Completed ingestion process for $REFERENCE_TIME in $PWD"
     cylc task-message $MSG

#     cd archive   #Only needed for old zope system
#     mv *.png ../                 #Extract these back out of the archive directory for later
   else
     MSG="Cannot find ${BASE_DIR}/areal; not processing areal data"
     cylc task-message $MSG
   fi
#
# Now do the Mintaka site specific xml files
   if [ -d ${BASE_DIR}/site_specific ]
   then
     cd $BASE_DIR/site_specific

     MSG="Starting ingestion process for $REFERENCE_TIME in $PWD"
     cylc task-message $MSG

#     ingest_xml_mult '-archive'
     ingest_xml_mult ./done        #On new system, move the data to .done for archiving later.
     MSG="Completed ingestion process for $REFERENCE_TIME in $PWD"
     cylc task-message $MSG
     cleanup
   else
     MSG="Cannot find ${BASE_DIR}/site_specific; not processing site_specific data"
     cylc task-message $MSG
   fi

# SUCCESS MESSAGE
cylc task-finished
    ;;
esac 
exit

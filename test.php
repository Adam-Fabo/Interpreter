<?php

// názov súboru: test.php
// autor: Adam Fabo (xfaboa00)
// program bol vytvorený na predmet IPP na FIT-e na VUT v Brne

// zapúzdrenie dat
class Data {
    public $parser_output = "";
    public $int_output   = "";
    public $filename = "";

}

// zapúzdrenie dat
class Files {
    public $file_src = "";
    public $file_in   = "";
    public $file_out = "";
    public $file_rc = "";

}
ini_set('display_errors','stderr');

//slúži na výsledné vygenerovanie html súboru
$html_output = [];

// zadefinovanie prepinacov
$shortopts  = "";
$longopts  = array(
    // : znaci Required value

    "help",
    "directory:",
    "recursive",
    "parse-script:",
    "int-script:",
    "parse-only",
    "int-only",
    "jexamxml:",
    "jexamcg:",
);

$options = getopt($shortopts, $longopts);


$parse_script_path = "parse.php";
$int_script_path   = "interpret.py";

$recursive = false;
$directory = "";

$parse_only = false;
$int_only = false;


// cesta na sukromnom pc
//$jexamxml_path = "jexaxml/jexamxml.jar";
//$jexamcfg_path = "options";

// cesta na merlinovi
$jexamxml_path = "/pub/courses/ipp/jexamxml/jexamxml.jar";
$jexamcfg_path = "/pub/courses/ipp/jexamxml/options";

// nezabudnut zmenit php na php7.4


// osetrenie parametrov
if (array_key_exists("help",$options)) {
    echo "Skript slouží pro automatické testování (postupné) aplikace
parse.php a interpret.py13. Skript projde zadaný adresář s testy a využije je pro automatické
otestování správné funkčnosti jednoho či obou předchozích skriptů včetně vygenerování přehledného
souhrnu v HTML 5 na standardní výstup.";

    if (count($options) != 1) {
        exit(10);
    }
    exit(0);
}

if (array_key_exists("parse-script",$options)) {
    $parse_script_path = $options["parse-script"];
}

if (array_key_exists("int-script",$options)) {
    $int_script_path = $options["int-script"];
}

if (array_key_exists("recursive",$options)) {
    $recursive = true;
}

if (array_key_exists("directory",$options)) {
    $directory = $options["directory"];
}

if (array_key_exists("parse-only",$options)) {
    $parse_only = true;
}

if (array_key_exists("int-only",$options)) {
    $int_only = true;
}

if (array_key_exists("jexamxml",$options)) {
    $jexamxml_path = $options["jexamxml"];
}

if (array_key_exists("jexamcfg ",$options)) {
    $jexamcfg_path = $options["jexamcfg"];
}


if($int_only and $parse_only)
    exit(10);

if(file_exists($parse_script_path) != true or file_exists($int_script_path) != true) {
    exit(41);
}

if(file_exists($jexamxml_path) != true or file_exists($jexamcfg_path) != true)
    exit(41);



// ziskanie ciest všetkých validných súborov
if($recursive) {
    $output = shell_exec(sprintf("find  %s -name \"*.src\"", $directory));
}
else {
    $output = shell_exec(sprintf("find  %s -maxdepth 1 -name \"*.src\"", $directory));
}

$output =  preg_split('/\s+/', trim($output));



$files = new Files();

// hlavná smyčka programu kde sa prechádza súbor za súborom
foreach ($output as $file){
    if (preg_match("/.*\.src$/", $directory.$file) != 1)
        continue;

    get_files($files,  $file);

    $file_src = $files->file_src ;
    $file_in = $files->file_in ;
    $file_out = $files->file_out ;
    $file_rc = $files->file_rc ;


    //var_dump($file);
    // jednotlivé módy parsera
    if($parse_only){

        $d = exec_parse_only($parse_script_path,$files,$jexamxml_path,$jexamcfg_path);
        array_push($html_output,$d);

    }else if($int_only){
        $d = exec_int_only($int_script_path,$files);
        array_push($html_output,$d);

    }else{
        $d = exec_both($parse_script_path,$int_script_path,$files);
        array_push($html_output,$d);
    }
}

generate_html($html_output,$parse_only,$int_only);
//koniec programu

// definície funkcií ------------------------------------------------------------------


// funkcia vykoná požadovanú funkčnosť testu na zadanom súbore, a to aj parsovanie a aj interpretáciu
function exec_both($parse_script_path,$int_script_path,$files){

    $file_src = $files->file_src ;
    $file_in = $files->file_in ;
    $file_out = $files->file_out ;
    $file_rc = $files->file_rc ;

    $tmp_xml = get_tmp_file_name("xml");

    $cmd = sprintf("php7.4 %s <%s >%s; echo $?",$parse_script_path, $file_src, $tmp_xml);
    $ret_code = intval(shell_exec($cmd));

    $f = fopen($file_rc,"r");
    $reference_code =  intval(fread($f, filesize($file_rc)));
    fclose($f);


    $d = new Data();
    $d->filename = $file_src;

    // ak narazil na chybu pri parse
    if($ret_code != 0){
        if($reference_code == $ret_code){
            $d->parser_output = sprintf("passed (expected: %d, got: %d)",$reference_code,$ret_code);
            $d->int_output = "not tested";

        }else{
            $d->parser_output = sprintf("failed (expected: %d, got: %d)",$reference_code,$ret_code);
            $d->int_output = "not tested";
        }
        shell_exec(sprintf("rm %s",$tmp_xml));
        return $d;
    }


    $tmp_out = get_tmp_file_name("out");
    $cmd = sprintf("python3.8 %s --source=%s --input=%s >%s; echo $?",$int_script_path, $tmp_xml, $file_in,$tmp_out);
    $ret_code = intval(shell_exec($cmd));

    if($ret_code != 0){
        if($reference_code == $ret_code){
            $d->parser_output = "passed";
            $d->int_output = sprintf("passed (expected: %d, got: %d)",$reference_code,$ret_code);

        }else{
            $d->parser_output = "passed";
            $d->int_output = sprintf("failed (expected: %d, got: %d)",$reference_code,$ret_code);
        }

        shell_exec(sprintf("rm %s",$tmp_xml));
        shell_exec(sprintf("rm %s",$tmp_out));
        return $d;
    }elseif ($ret_code == 0 && $reference_code !=0){
        //dostal som z oboch 0 ale mal som dotat nieco ine

        $d->parser_output = "failed";
        $d->int_output = sprintf("failed (expected: %d, but got 0 from both (int and parse))",$reference_code);


        shell_exec(sprintf("rm %s",$tmp_xml));
        shell_exec(sprintf("rm %s",$tmp_out));
        return $d;
    }

    shell_exec(sprintf("rm %s",$tmp_xml));


    $cmd = sprintf("diff %s %s; echo $?",$file_out,$tmp_out);
    $ret_code = intval(shell_exec($cmd));

    if($ret_code == 0){
        $d->int_output = sprintf("passed");
        $d->parser_output = "passed";

    }else{
        $d->int_output = sprintf("failed - different output, checked with diff");
        $d->parser_output = "passed";
    }

    shell_exec(sprintf("rm %s",$tmp_out));
    return $d;

}

// funkcia vykoná požadovanú funkčnosť testu na zadanom súbore, ak bol spustený s prepínačom --int-only
function exec_int_only($int_script_path,$files){
    $file_src = $files->file_src ;
    $file_in = $files->file_in ;
    $file_out = $files->file_out ;
    $file_rc = $files->file_rc ;

    $tmp_out = get_tmp_file_name("out");

    $cmd = sprintf("python3.8 %s --source=%s --input=%s >%s; echo $?",$int_script_path, $file_src, $file_in,$tmp_out);
    $ret_code = intval(shell_exec($cmd));

    $f = fopen($file_rc,"r");
    $reference_code =  intval(fread($f, filesize($file_rc)));
    fclose($f);

    $d = new Data();
    $d->filename = $file_src;

    if($ret_code != $reference_code){
        $d->int_output = sprintf("failed (expected: %d, got: %d)",$reference_code,$ret_code);
        $d->parser_output = "not tested";

        shell_exec(sprintf("rm %s",$tmp_out));
        return $d;

    }else if($ret_code == $reference_code and $ret_code !=0){
        $d->int_output = sprintf("passed (expected: %d, got: %d)",$reference_code,$ret_code);
        $d->parser_output = "not tested";

        shell_exec(sprintf("rm %s",$tmp_out));
        return $d;
    }

    $cmd = sprintf("diff %s %s; echo $?",$file_out,$tmp_out);
    $ret_code = intval(shell_exec($cmd));

    if($ret_code == 0){
        $d->int_output = sprintf("passed");
        $d->parser_output = "not tested";

    }else{
        $d->int_output = sprintf("failed - different output, checked with diff");
        $d->parser_output = "not tested";
    }

    //shell_exec(sprintf("rm %s",$tmp_out));
    shell_exec(sprintf("rm %s",$tmp_out));
    return $d;



}

// funkcia vykoná požadovanú funkčnosť testu na zadanom súbore, ak bol spustený s prepínačom --parse-only
function exec_parse_only($parse_script_path,$files,$jexamxml_path,$jexamcfg_path){

    $file_src = $files->file_src ;
    $file_in = $files->file_in ;
    $file_out = $files->file_out ;
    $file_rc = $files->file_rc ;

    $tmp_xml = get_tmp_file_name("xml");

    $cmd = sprintf("php7.4 %s <%s >%s; echo $?",$parse_script_path, $file_src, $tmp_xml);
    $ret_code = intval(shell_exec($cmd));

    $f = fopen($file_rc,"r");
    $reference_code =  intval(fread($f, filesize($file_rc)));
    fclose($f);

    $d = new Data();
    $d->filename = $file_src;

    if($ret_code != $reference_code){
        $d->parser_output = sprintf("failed (expected: %d, got: %d)",$reference_code,$ret_code);
        $d->int_output = "not tested";

        shell_exec(sprintf("rm %s",$tmp_xml));
        return $d;

    }else if($ret_code == $reference_code and $ret_code !=0){
        $d->parser_output = sprintf("passed (expected: %d, got: %d)",$reference_code,$ret_code);
        $d->int_output = "not tested";

        shell_exec(sprintf("rm %s",$tmp_xml));
        return $d;

    }

    $tmp_delta_xml = get_tmp_file_name("log");

    //java -jar /pub/courses/ipp/jexamxml/jexamxml.jar vas_vystup.xml referencni.xml delta.xml /pub/courses/ipp/jexamxml/options

    $format_jexaxml = "java -jar %s %s %s %s %s >/dev/null; echo $?";
    $cmd = sprintf($format_jexaxml,$jexamxml_path,$tmp_xml,$file_out,$tmp_delta_xml,$jexamcfg_path);
    $ret_code = (shell_exec($cmd));

    if($ret_code == 0){
        $d->parser_output = sprintf("passed");
        $d->int_output = "not tested";

    }else{
        $d->parser_output = sprintf("failed - different xml output");
        $d->int_output = "not tested";
    }

    if(file_exists($tmp_delta_xml."log")) shell_exec(sprintf("rm %s.log",$tmp_delta_xml));
    if(file_exists($tmp_xml)) shell_exec(sprintf("rm %s",$tmp_xml));
    if(file_exists($tmp_xml."log")) shell_exec(sprintf("rm %s.log",$tmp_xml));
    if(file_exists($tmp_delta_xml)) shell_exec(sprintf("rm %s",$tmp_delta_xml));


    return $d;
}

// funkcia zistí či exitujú všetky potrebné subory (.in .out .rc), a ak nie tak ich dogeneruje
function get_files($files, $file_src){

    $file_in = str_lreplace(".src",".in",$file_src);
    if(file_exists($file_in) != true){
        $f = fopen($file_in,"w");
        fclose($f);
    }

    $file_out = str_lreplace(".src",".out",$file_src);
    if(file_exists($file_out) != true){
        $f = fopen($file_out,"w");
        fclose($f);
    }

    $file_rc = str_lreplace(".src",".rc",$file_src);
    if(file_exists($file_rc) != true){
        $f = fopen($file_rc,"w");
        echo"0";
        fclose($f);
    }

    $files->file_src = $file_src;
    $files->file_in  = $file_in;
    $files->file_out = $file_out;
    $files->file_rc  = $file_rc;

}


// vygeneruje vysledne html
function generate_html($html_output, $parse_only, $int_only){
    $total = 0;
    $succ = 0;
    //var_dump($html_output);

    // spočítanie dobrých a zlých testov
    if($parse_only){
        foreach ($html_output as $line) {
            $total++;
            //var_dump($line->parse_output);
            if(strpos($line->parse_output,"passed") !== false) {
                $succ++;
            }
        }

    }else if($int_only){
        foreach ($html_output as $line) {
            $total++;
            //var_dump($line->int_output);
            if(strpos($line->int_output,"passed") !== false) {
                $succ++;
            }
        }

    }else {
        foreach ($html_output as $line) {
            $total++;
            if (strpos($line->parser_output, "passed") !== false) {
                if (strpos($line->int_output, "passed") !== false) {
                    $succ++;
                } else if (strpos($line->int_output, "not tested") !== false) {
                    $succ++;
                }
            }
        }
    }

    //$f = fopen("report_page.html","w");

    //vypise hlavicku ktora je rovnaka pre vsetky vypisky
    write_html_header($succ,$total);


    if( $parse_only == true) {


        echo '<pre class="tab" style = "font-size:15px ">Mode: parse only</pre>';
        echo "\n";
        echo "<pre class=\"tab\" style = \"font-size:15px \"> </pre>\n";


        foreach ($html_output as $line) {
            write_html_parse_only($line);
        }


    }else if( $int_only) {

        echo '<pre class="tab" style = "font-size:15px ">Mode: interpret only</pre>';
        echo "\n";
        echo "<pre class=\"tab\" style = \"font-size:15px \"> </pre>\n";


        foreach ($html_output as $line) {
            write_html_int_only($line);
        }

    }else{

        foreach ($html_output as $line) {
            write_html_both($line);
        }


    }


    echo"</body>";
    echo"\n";
    echo"</html>";
    echo"\n";

    //fclose($f);

}

// používa sa na zapísanie jedného riadku do html súboru ak je test v móde prase aj int
function write_html_both($line){

    $format_str = '<pre class="tab" style="color:%s; font-size:15px ">%s          parse: %s          interpert: %s</pre>';

    $filename= str_pad($line->filename,50," ",STR_PAD_RIGHT);
    $parser_output= str_pad($line->parser_output,20," ",STR_PAD_RIGHT);
    $int_output= str_pad($line->int_output,20," ",STR_PAD_RIGHT);

    if(strpos($line->parser_output,"passed") !== false) {
        if(strpos($line->int_output,"passed") !== false) {
            echo sprintf($format_str,"limegreen",$filename, $parser_output, $int_output);
            echo"\n";

        }else if(strpos($line->int_output,"not tested") !== false){
            echo sprintf($format_str,"limegreen",$filename, $parser_output, $int_output);
            echo"\n";

        }else{
            echo sprintf($format_str,"red",$filename, $parser_output, $int_output);
            echo"\n";
        }

    }else{
        echo sprintf($format_str,"red",$filename, $parser_output, $int_output);
        echo"\n";

    }



}

// používa sa na zapísanie jedného riadku do html súboru ak je test v móde int only
function write_html_int_only($line){

    $format_str = '<pre class="tab" style="color:%s; font-size:15px ">%s          interpret: %s</pre>';

    $filename= str_pad($line->filename,50," ",STR_PAD_RIGHT);
    $int_output= str_pad($line->int_output,20," ",STR_PAD_RIGHT);


    if(strpos($line->int_output,"passed") !== false) {
        $str = sprintf($format_str,"limegreen",$filename, $int_output);
    }else{
        $str = sprintf($format_str,"red",$filename, $int_output);
    }
    echo $str;
    echo "\n";


}

// používa sa na zapísanie jedného riadku do html súboru ak je test v móde prase only
function write_html_parse_only($line){
    $format_str = '<pre class="tab" style="color:%s; font-size:15px ">%s          parse: %s</pre>';

    $filename= str_pad($line->filename,50," ",STR_PAD_RIGHT);
    $parser_output= str_pad($line->parser_output,20," ",STR_PAD_RIGHT);


    if(strpos($line->parser_output,"passed") !== false) {
        $str = sprintf($format_str,"limegreen",$filename, $parser_output);
    }else{
        $str = sprintf($format_str,"red",$filename, $parser_output);
    }
    echo $str;
    echo "\n";


}

//zapíše hlavičku html súboru
function write_html_header($succ,$total){
    //var_dump($succ);
    //var_dump($total);

    echo"<!DOCTYPE html>\n";
    echo"<html lang=\"en\">\n";
    echo"<meta charset=\"UTF-8\">\n";
    echo"<title>IPP</title>\n";
    echo"<body>\n";

    echo "<pre class=\"tab\" style = \"font-size:15px \">IPP report page</pre>\n";
    echo "<pre class=\"tab\" style = \"font-size:15px \">Author: Adam Fabo [xfaboa00]</pre>\n";
    echo "<pre class=\"tab\" style = \"font-size:15px \"> </pre>\n";


    $str = "<pre class=\"tab\" style = \"font-size:15px \">Passed: %d  Failed: %d</pre>\n";
    echo sprintf($str,$succ,$total-$succ);
    echo "<pre class=\"tab\" style = \"font-size:15px \"> </pre>\n";


}

// získa nový originálny názov súboru, pričom type je typ súboru (napr html)
function get_tmp_file_name($type){
    $f = sprintf("tmp_file.%s",$type);

    $c = 0;
    while (file_exists($f) == true){
        $f = sprintf("tmp_file_%d.%s",$c,$type);
        $c++;
    }
    return $f;

}


// funkcia prevzata z:
// https://stackoverflow.com/questions/3835636/replace-last-occurrence-of-a-string-in-a-string
function str_lreplace($search, $replace, $subject)
{
    $pos = strrpos($subject, $search);

    if($pos !== false)
    {
        $subject = substr_replace($subject, $replace, $pos, strlen($search));
    }

    return $subject;
}

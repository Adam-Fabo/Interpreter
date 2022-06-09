<?php

// Author: Adam Fabo
// Name: test.php
// File is part of project at VUT FIT - subject IPP



// možné návratové kódy
// 10 - zle parametre
// 21 - chybná nebo chybějící hlavička ve zdrojovém kódu zapsaném v IPPcode21;
// 22 - neznámý nebo chybný operační kód ve zdrojovém kódu zapsaném v IPPcode21;
// 23 - jiná lexikální nebo syntaktická chyba zdrojového kódu zapsaného v IPPcode21.


ini_set('display_errors','stderr');

//ošetrienie argumentov
if($argc > 1){

    if($argv[1] == "--help"){

        echo("Tento program sa pouziva na prevedenie kodu IPPcode21 do XML formatu, pricom prevadza syntakticke a semnaticke kontroly\n");
        echo("IPPcode21 nacita z stdin a xml subor vypise na stdout");
        exit(0);
    }else{
        print_r($argv);
        exit(10);
    }
}elseif ($argc > 2){
    exit(10);
}

$header = false;
$ins_count = 1;
$arg_count = 0;

// formáty vypisu jednotlivách XML elementov
$instruction_single = "\t<instruction order=\"%d\" opcode=\"%s\"/>\n";
$instruction_begin = "\t<instruction order=\"%d\" opcode=\"%s\">\n";
$instruction_end = "\t</instruction>\n";

$arg = "\t\t<arg%d type=\"%s\">%s</arg%d>\n";

// začiatočná hlavička xml súboru
echo("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n");
echo("<program language=\"IPPcode21\">\n");


// hlavná smyčka programu
while($line = fgets(STDIN)){

    $line = preg_replace("/#.*/", " ",$line); //odstránenie komentárov

    $line = trim($line);

    if(ctype_space($line)) {                                     //ak je prázdny riadok - continue
        continue;
    }

    if($line == "")
        continue;


    if($header == false){
        if($line == ".IPPcode21") {                              // po prvotných prázdnych riadkoch prvý normálny riadok
            $header = true;                                      // musí byť .IPPcode21
            continue;
        }else {
            exit(21);
        }
    }

    $splitted = preg_split('/\s+/', $line);             // split riadku


    switch( strtoupper($splitted[0])){

        // 0 parametrov *******************************

        case "CREATEFRAME":
        case "PUSHFRAME":
        case "POPFRAME":
        case "RETURN":
        case "BREAK":
            if(count($splitted) != 1)
                exit(23);

            echo sprintf($instruction_single,$ins_count,strtoupper($splitted[0]));
            $ins_count++;
            break;

        // 1 parameter *******************************
        case "DEFVAR":
        case "POPS":

            if(count($splitted) != 2)
                exit(23);

            echo sprintf($instruction_begin,$ins_count,strtoupper($splitted[0]));

            if( my_var($arg,1,$splitted[1]) == false){
                exit(23);
            }

            echo $instruction_end;
            $ins_count++;
            break;

        case "CALL":
        case "LABEL":
        case "JUMP":

            if(count($splitted) != 2)
                exit(23);

            echo sprintf($instruction_begin,$ins_count,strtoupper($splitted[0]));

            if( my_label($arg,1,$splitted[1]) == false){
                exit(23);
            }
            echo $instruction_end;
            $ins_count++;
            break;

        case "PUSHS":
        case "WRITE":
        case "EXIT":
        case "DPRINT":

            if(count($splitted) != 2)
                exit(23);

            echo sprintf($instruction_begin,$ins_count,strtoupper($splitted[0]));
            if( my_symb($arg,1,$splitted[1]) == false){
                exit(23);
            }
            echo $instruction_end;
            $ins_count++;
            break;

        // 2 parametre *******************************
        case "MOVE":
        case "INT2CHAR":
        case "STRLEN":
        case "TYPE":
        case "NOT":

            if(count($splitted) != 3) {
                exit(23);
            }


            echo sprintf($instruction_begin,$ins_count,strtoupper($splitted[0]));
            if( my_var($arg,1,$splitted[1]) == false){
                exit(23);
            }
            if( my_symb($arg,2,$splitted[2]) == false){
                exit(23);
            }
            echo $instruction_end;
            $ins_count++;
            break;

        case "READ":
            if(count($splitted) != 3)
                exit(23);


            echo sprintf($instruction_begin,$ins_count,strtoupper($splitted[0]));
            if( my_var($arg,1,$splitted[1]) == false){
                exit(23);
            }
            if( my_type($arg,2,$splitted[2]) == false){
                exit(23);
            }
            echo $instruction_end;
            $ins_count++;
            break;

        // 3 parametre *******************************
        case "ADD":
        case "SUB":
        case "MUL":
        case "IDIV":
        case "LT":
        case "GT":
        case "EQ":
        case "AND":
        case "OR":
        case "STRI2INT":
        case "CONCAT":
        case "GETCHAR":
        case "SETCHAR":
            if(count($splitted) != 4)
                exit(23);


            echo sprintf($instruction_begin,$ins_count,strtoupper($splitted[0]));

            if( my_var($arg,1,$splitted[1]) == false){
                exit(23);
            }
            if( my_symb($arg,2,$splitted[2]) == false){
                exit(23);
            }
            if( my_symb($arg,3,$splitted[3]) == false){
                exit(23);
            }

            echo $instruction_end;
            $ins_count++;
            break;

        case "JUMPIFEQ":
        case "JUMPIFNEQ":
            if(count($splitted) != 4)
                exit(23);


            echo sprintf($instruction_begin,$ins_count,strtoupper($splitted[0]));

            if( my_label($arg,1,$splitted[1]) == false){
                exit(23);
            }
            if( my_symb($arg,2,$splitted[2]) == false){
                exit(23);
            }
            if( my_symb($arg,3,$splitted[3]) == false){
                exit(23);
            }

            echo $instruction_end;
            $ins_count++;
            break;
        default:
            exit(22);
    }

}


echo "</program>\n";    // ukončenie výpisu
exit(0);

// funkcia spracuje zadaný reťazec $name
// ak sedí typ var, tak ho rovno zapíše ako argument do XML súboru
// $arg je formátovací reťazec pre zápis do XML súboru
function my_var($arg,$arg_num,$name){

    $var_regex = "/^(LF|TF|GF)@[\p{L}_\-$&%*!?][0-9\p{L}_\-$&%*!?]*$/";

     if( preg_match($var_regex, $name) == 1){
         $name = htmlspecialchars($name);
         echo sprintf($arg,$arg_num,"var",$name, $arg_num);
         return true;
     } else{
         return false;
     }
}

// funkcia spracuje zadaný reťazec $name
// ak sedí typ type, tak ho rovno zapíše ako argument do XML súboru
// $arg je formátovací reťazec pre zápis do XML súboru
function my_type($arg,$arg_num,$name){

    $type_regex = "/^(string|int|bool)$/";

    if( preg_match($type_regex, $name) == 1){
        echo sprintf($arg,$arg_num,"type",$name, $arg_num);
        return true;
    } else{
        return false;
    }
}

// funkcia spracuje zadaný reťazec $name
// ak sedí typ label, tak ho rovno zapíše ako argument do XML súboru
// $arg je formátovací reťazec pre zápis do XML súboru
function my_label($arg,$arg_num,$name){

    $label_regex = "/^[\p{L}_\-$&%*!?][0-9\p{L}_\-$&%*!?]*$/";

    if( preg_match($label_regex, $name) == 1){
        echo sprintf($arg,$arg_num,"label",$name, $arg_num);
        return true;
    } else{
        return false;
    }
}

// funkcia spracuje zadaný reťazec $name
// ak sedí typ patrý medzi podtypy symb, tak ho rovno zapíše ako argument do XML súboru
// $arg je formátovací reťazec pre zápis do XML súboru
function my_symb($arg,$arg_num,$name){

    $var_regex = "/^(LF|TF|GF)@[\p{L}_\-$&%*!?][0-9\p{L}_\-$&%*!?]*$/";

    $string_regex = "/^string@/"; // [^#\\\]*$
    $string_regex_escape = "/\\\\([^0-9]{1}|[0-9][^0-9]|[0-9]{2}[^0-9])/";    // zisti ci sa v stringu nachadzaju nejake chybne escape seq

    $int_regex = "/^int@/";
    $bool_regex = "/^bool@(true|false)$/";
    $nil_regex = "/^nil@nil$/";


    if( preg_match($var_regex, $name) == 1){
        echo sprintf($arg,$arg_num,"var",$name, $arg_num);
        return true;

    }elseif (preg_match($string_regex, $name) == 1){

        $name = htmlspecialchars($name);

        if( preg_match($string_regex_escape, $name) == 1 or strpos (substr($name, -3), "\\"))
            return false;


        if(substr($name, 7) == "") {
            $arg_shortened = "\t\t<arg%d type=\"%s\"/>";
            echo sprintf($arg_shortened, $arg_num, "string", substr($name, 7), $arg_num);

        }else {
            echo sprintf($arg, $arg_num, "string", substr($name, 7), $arg_num);
        }

        return true;
    }elseif (preg_match($int_regex, $name) == 1){
        echo sprintf($arg,$arg_num,"int",substr($name,4), $arg_num);
        return true;

    }elseif (preg_match($bool_regex, $name) == 1){
        echo sprintf($arg,$arg_num,"bool",str_replace("bool@", "", $name), $arg_num);
        return true;

    }elseif (preg_match($nil_regex, $name) == 1){
        echo sprintf($arg,$arg_num,"nil",str_replace("nil@", "", $name), $arg_num);
        return true;

    }else{
        return false;
    }
}



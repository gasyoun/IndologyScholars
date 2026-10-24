_Created: 15-08-2026 · Last updated: 05-09-2026_

---
thread_id: 21976148082688
subject: "IAST extension for SanDic"
year: 2013
messages: 14
participants: "śrīdṛṣṭvā, Marcis, Artem Novikov"
first: 2013-03-13T17:53:13+03:00
last: 2013-03-19T17:50:00+03:00
source_url: https://groups.google.com/d/msgid/nagari/adf27f6c-bb88-405b-b058-9096c7058d40@googlegroups.com
---

# IAST extension for SanDic

[Читать оригинальный тред в Google Groups](https://groups.google.com/d/msgid/nagari/adf27f6c-bb88-405b-b058-9096c7058d40@googlegroups.com)

> 14 сообщений · 3 участников · 2013-03-13 — 2013-03-19

## 1. śrīdṛṣṭvā — 2013-03-13 17:53:13

Today is a good day)

Now, I feel totally free from ITRANS, because I modified itrans.cpp, 

itrans.h of SanDic sources.

It still support ITRANS, with the only exception, now I type ca-cha instead 

of cha-Cha. So any letter can be typed with both standards, IAST is just 

extension.

So here is sources itrans.cpp:

/*=========================================================================== 



    SanDic, Sanscrit-English Dictionary 

    Copyright (C) 2012 Novikov Artem Gennadievich , with IAST extension by 

śrīdṛṣṭvā



    This program is free software: you can redistribute it and/or modify 

    it under the terms of the GNU General Public License as published by 

    the Free Software Foundation, either version 3 of the License, or 

    (at your option) any later version. 

 

    This program is distributed in the hope that it will be useful, 

    but WITHOUT ANY WARRANTY; without even the implied warranty of 

    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the 

    GNU General Public License for more details. 

 

    You should have received a copy of the GNU General Public License 

    along with this program.  If not, see <http://www.gnu.org/licenses/> 

===========================================================================*/ 

 

#include "itrans.h" 

 

ItransDecoder::ItransDecoder() 

{ 

    map[0] << ItransMapItem("aa",  "A",  QChar(0x0101),  0x0906) 

           << ItransMapItem("ii",  "I",   QChar(0x012b), 0x0908) 

           << ItransMapItem("uu",  "U",   QChar(0x016b), 0x090a) 

           << ItransMapItem("RRi", "R^i", QChar(0x1e5b), 0x090b) 

           << ItransMapItem("RRI", "R^I", QChar(0x1e5d), 0x0960) 

           << ItransMapItem("LLi", "L^i", QChar(0x1e37), 0x090c) 

           << ItransMapItem("LLI", "L^I", QChar(0x1e39), 0x0961) 

           << ItransMapItem("ai", 0x0910) 

           << ItransMapItem("au", 0x0914) 

           << ItransMapItem("a",  0x0905) 

           << ItransMapItem("i",  0x0907) 

           << ItransMapItem("u",  0x0909) 

           << ItransMapItem("e",  QChar(0x0113), 0x090f) 

           << ItransMapItem("o",  QChar(0x014d), 0x0913) 

           << ItransMapItem("M",  QChar(0x1e43), 0x0902) 

           << ItransMapItem("H",  QChar(0x1e25), 0x0903); 

    map[1] << ItransMapItem("aa",  "A",  QChar(0x0101), 0x093e) 

           << ItransMapItem("ii",  "I",   QChar(0x012b), 0x0940) 

           << ItransMapItem("uu",  "U",   QChar(0x016b), 0x0942) 

           << ItransMapItem("RRi", "R^i", QChar(0x1e5b), 0x0943) 

           << ItransMapItem("RRI", "R^I", QChar(0x1e5d), 0x0944) 

           << ItransMapItem("ai", 0x0948) 

           << ItransMapItem("au", 0x094C) 

           << ItransMapItem("i",  0x093f) 

           << ItransMapItem("u",  0x0941) 

           << ItransMapItem("e",  QChar(0x0113), 0x0947) 

           << ItransMapItem("o",  QChar(0x014d), 0x094b); 

    map[2] << ItransMapItem("kh", 0x0916) 

           << ItransMapItem("gh", 0x0918) 

           << ItransMapItem("~N", QChar(0x1e45), 0x0919) 

//           << ItransMapItem("ch", 0x091a) 

//           << ItransMapItem("Ch", 0x091b) 

           << ItransMapItem("ch", 0x091b) 

           << ItransMapItem("jh", 0x091d) 

           << ItransMapItem("~n", QChar(0x00f1), 0x091e) 

           << ItransMapItem("Th", QString("%1h").arg(QChar(0x1e6d)), 0x0920) 

           << ItransMapItem("Dh", QString("%1h").arg(QChar(0x1e0d)), 0x0922) 

           << ItransMapItem("th", 0x0925) 

           << ItransMapItem("dh", 0x0927) 

           << ItransMapItem("ph", 0x092b) 

           << ItransMapItem("bh", 0x092d) 

           << ItransMapItem("sh",  QChar(0x015b), 0x0936) 

           << ItransMapItem("Sh",  QChar(0x1e63), 0x0937) 

           << ItransMapItem("k",  0x0915) 

           << ItransMapItem("g",  0x0917) 

           << ItransMapItem("c",  0x091a) 

           << ItransMapItem("j",  0x091c) 

           << ItransMapItem("T",  QChar(0x1e6d), 0x091f) 

           << ItransMapItem("D",  QChar(0x1e0d), 0x0921) 

           << ItransMapItem("N",  QChar(0x1e47), 0x0923) 

           << ItransMapItem("t",  0x0924) 

           << ItransMapItem("d",  0x0926) 

           << ItransMapItem("n",  0x0928) 

           << ItransMapItem("p",  0x092a) 

           << ItransMapItem("b",  0x092c) 

           << ItransMapItem("m",  0x092e) 

           << ItransMapItem("y",  0x092f) 

           << ItransMapItem("r",  0x0930) 

           << ItransMapItem("l",  0x0932) 

           << ItransMapItem("v", "w", 0x0935) 

           << ItransMapItem("w",  0x0935) 

           << ItransMapItem("s",  0x0938) 

           << ItransMapItem("h",  0x0939) 

           << ItransMapItem("L",  0x0933); 

    map[3] << ItransMapItem("0",  0x0966) 

           << ItransMapItem("1",  0x0967) 

           << ItransMapItem("2",  0x0968) 

           << ItransMapItem("3",  0x0969) 

           << ItransMapItem("4",  0x096a) 

           << ItransMapItem("5",  0x096b) 

           << ItransMapItem("6",  0x096c) 

           << ItransMapItem("7",  0x096d) 

           << ItransMapItem("8",  0x096e) 

           << ItransMapItem("9",  0x096f); 

} 

 

QString ItransDecoder::decode(QString txt) 

{ 

    for (int i = 0; i < map[2].count(); i++) // consonant + virama 

        txt.replace(QRegExp(map[2][i].txt), QString("%1%2").arg(QChar(map[2

][i].code), QChar(0x094d))); 

 

    for (int i = 0; i < map[1].count(); i++) // consonant - virama + vowels 

sign short 

        txt.replace(QRegExp(QString("([\\x0915-\\x0939])\\x094d%1").arg(map[

1][i].txt)), QString("\\1%1").arg(QChar(map[1][i].code))); 

 

    txt.replace(QRegExp("([\\x0915-\\x0939])\\x094da"), QString("\\1")); // 

"a" 0x0000 

 

    for (int i = 0; i < map[0].count(); i++) 

        txt.replace(QRegExp(map[0][i].txt), QChar(map[0][i].code)); 

 

    for (int i = 0; i < map[3].count(); i++) 

        txt.replace(QRegExp(map[3][i].txt), QChar(map[3][i].code)); 

 

    return txt; 

}







The only modification of itrans.h is there-case replace of QString:

struct ItransMapItem

{

    ItransMapItem(QString txt, int code)

        : txt(REPLACE(txt)), code(code) {}

    ItransMapItem(QString txt1, QString txt2, int code)

        : txt(REPLACE(QString("(%1|%2)").arg(txt1, txt2))), code(code) {}

    ItransMapItem(QString txt1, QString txt2, QString txt3, int code)

        : txt(REPLACE(QString("(%1|%2|%3)").arg(txt1, txt2, txt3))), code(

code) {}



    QString txt;

    int     code;

};

## 2. śrīdṛṣṭvā — 2013-03-13 17:59:06

Oh, forgot - screenshot

http://s17.postimage.org/qylwe4mgt/Screenshot_from_2013_03_13_07_43_54.png



On Wednesday, March 13, 2013 7:53:13 AM UTC-7, śrīdṛṣṭvā wrote:

>

> Today is a good day)

> Now, I feel totally free from ITRANS, because I modified itrans.cpp, 

> itrans.h of SanDic sources.

> It still support ITRANS, with the only exception, now I type ca-cha 

> instead of cha-Cha. So any letter can be typed with both standards, IAST is 

> just extension.

> So here is sources itrans.cpp:

> /*=========================================================================== 

>

>     SanDic, Sanscrit-English Dictionary 

>     Copyright (C) 2012 Novikov Artem Gennadievich , with IAST extension by 

> śrīdṛṣṭvā

>

>     This program is free software: you can redistribute it and/or modify 

>     it under the terms of the GNU General Public License as published by 

>     the Free Software Foundation, either version 3 of the License, or 

>     (at your option) any later version. 

>  

>     This program is distributed in the hope that it will be useful, 

>     but WITHOUT ANY WARRANTY; without even the implied warranty of 

>     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the 

>     GNU General Public License for more details. 

>  

>     You should have received a copy of the GNU General Public License 

>     along with this program.  If not, see <http://www.gnu.org/licenses/> 

>

> ===========================================================================*/ 

>  

> #include "itrans.h" 

>  

> ItransDecoder::ItransDecoder() 

> { 

>     map[0] << ItransMapItem("aa",  "A",  QChar(0x0101),  0x0906) 

>            << ItransMapItem("ii",  "I",   QChar(0x012b), 0x0908) 

>            << ItransMapItem("uu",  "U",   QChar(0x016b), 0x090a) 

>            << ItransMapItem("RRi", "R^i", QChar(0x1e5b), 0x090b) 

>            << ItransMapItem("RRI", "R^I", QChar(0x1e5d), 0x0960) 

>            << ItransMapItem("LLi", "L^i", QChar(0x1e37), 0x090c) 

>            << ItransMapItem("LLI", "L^I", QChar(0x1e39), 0x0961) 

>            << ItransMapItem("ai", 0x0910) 

>            << ItransMapItem("au", 0x0914) 

>            << ItransMapItem("a",  0x0905) 

>            << ItransMapItem("i",  0x0907) 

>            << ItransMapItem("u",  0x0909) 

>            << ItransMapItem("e",  QChar(0x0113), 0x090f) 

>            << ItransMapItem("o",  QChar(0x014d), 0x0913) 

>            << ItransMapItem("M",  QChar(0x1e43), 0x0902) 

>            << ItransMapItem("H",  QChar(0x1e25), 0x0903); 

>     map[1] << ItransMapItem("aa",  "A",  QChar(0x0101), 0x093e) 

>            << ItransMapItem("ii",  "I",   QChar(0x012b), 0x0940) 

>            << ItransMapItem("uu",  "U",   QChar(0x016b), 0x0942) 

>            << ItransMapItem("RRi", "R^i", QChar(0x1e5b), 0x0943) 

>            << ItransMapItem("RRI", "R^I", QChar(0x1e5d), 0x0944) 

>            << ItransMapItem("ai", 0x0948) 

>            << ItransMapItem("au", 0x094C) 

>            << ItransMapItem("i",  0x093f) 

>            << ItransMapItem("u",  0x0941) 

>            << ItransMapItem("e",  QChar(0x0113), 0x0947) 

>            << ItransMapItem("o",  QChar(0x014d), 0x094b); 

>     map[2] << ItransMapItem("kh", 0x0916) 

>            << ItransMapItem("gh", 0x0918) 

>            << ItransMapItem("~N", QChar(0x1e45), 0x0919) 

> //           << ItransMapItem("ch", 0x091a) 

> //           << ItransMapItem("Ch", 0x091b) 

>            << ItransMapItem("ch", 0x091b) 

>            << ItransMapItem("jh", 0x091d) 

>            << ItransMapItem("~n", QChar(0x00f1), 0x091e) 

>            << ItransMapItem("Th", QString("%1h").arg(QChar(0x1e6d)), 

> 0x0920) 

>            << ItransMapItem("Dh", QString("%1h").arg(QChar(0x1e0d)), 

> 0x0922) 

>            << ItransMapItem("th", 0x0925) 

>            << ItransMapItem("dh", 0x0927) 

>            << ItransMapItem("ph", 0x092b) 

>            << ItransMapItem("bh", 0x092d) 

>            << ItransMapItem("sh",  QChar(0x015b), 0x0936) 

>            << ItransMapItem("Sh",  QChar(0x1e63), 0x0937) 

>            << ItransMapItem("k",  0x0915) 

>            << ItransMapItem("g",  0x0917) 

>            << ItransMapItem("c",  0x091a) 

>            << ItransMapItem("j",  0x091c) 

>            << ItransMapItem("T",  QChar(0x1e6d), 0x091f) 

>            << ItransMapItem("D",  QChar(0x1e0d), 0x0921) 

>            << ItransMapItem("N",  QChar(0x1e47), 0x0923) 

>            << ItransMapItem("t",  0x0924) 

>            << ItransMapItem("d",  0x0926) 

>            << ItransMapItem("n",  0x0928) 

>            << ItransMapItem("p",  0x092a) 

>            << ItransMapItem("b",  0x092c) 

>            << ItransMapItem("m",  0x092e) 

>            << ItransMapItem("y",  0x092f) 

>            << ItransMapItem("r",  0x0930) 

>            << ItransMapItem("l",  0x0932) 

>            << ItransMapItem("v", "w", 0x0935) 

>            << ItransMapItem("w",  0x0935) 

>            << ItransMapItem("s",  0x0938) 

>            << ItransMapItem("h",  0x0939) 

>            << ItransMapItem("L",  0x0933); 

>     map[3] << ItransMapItem("0",  0x0966) 

>            << ItransMapItem("1",  0x0967) 

>            << ItransMapItem("2",  0x0968) 

>            << ItransMapItem("3",  0x0969) 

>            << ItransMapItem("4",  0x096a) 

>            << ItransMapItem("5",  0x096b) 

>            << ItransMapItem("6",  0x096c) 

>            << ItransMapItem("7",  0x096d) 

>            << ItransMapItem("8",  0x096e) 

>            << ItransMapItem("9",  0x096f); 

> } 

>  

> QString ItransDecoder::decode(QString txt) 

> { 

>     for (int i = 0; i < map[2].count(); i++) // consonant + virama 

>         txt.replace(QRegExp(map[2][i].txt), QString("%1%2").arg(QChar(map[

> 2][i].code), QChar(0x094d))); 

>  

>     for (int i = 0; i < map[1].count(); i++) // consonant - virama + 

> vowels sign short 

>         txt.replace(QRegExp(QString("([\\x0915-\\x0939])\\x094d%1").arg(

> map[1][i].txt)), QString("\\1%1").arg(QChar(map[1][i].code))); 

>  

>     txt.replace(QRegExp("([\\x0915-\\x0939])\\x094da"), QString("\\1")); // 

> "a" 0x0000 

>  

>     for (int i = 0; i < map[0].count(); i++) 

>         txt.replace(QRegExp(map[0][i].txt), QChar(map[0][i].code)); 

>  

>     for (int i = 0; i < map[3].count(); i++) 

>         txt.replace(QRegExp(map[3][i].txt), QChar(map[3][i].code)); 

>  

>     return txt; 

> }

>

>

>

> The only modification of itrans.h is there-case replace of QString:

> struct ItransMapItem

> {

>     ItransMapItem(QString txt, int code)

>         : txt(REPLACE(txt)), code(code) {}

>     ItransMapItem(QString txt1, QString txt2, int code)

>         : txt(REPLACE(QString("(%1|%2)").arg(txt1, txt2))), code(code) {}

>     ItransMapItem(QString txt1, QString txt2, QString txt3, int code)

>         : txt(REPLACE(QString("(%1|%2|%3)").arg(txt1, txt2, txt3))), code(

> code) {}

>

>     QString txt;

>     int     code;

> };

>

## 3. Marcis — 2013-03-14 09:13:14

Скриншоты лучше цеплять здесь, ибо сторонние ссылки имеют тенденцию 

умирать. Что за шрифт поменяли, куда ушли от Siddhanta?



среда, 13 марта 2013 г., 18:59:06 UTC+4 пользователь śrīdṛṣṭvā написал:

>

> Oh, forgot - screenshot

> http://s17.postimage.org/qylwe4mgt/Screenshot_from_2013_03_13_07_43_54.png

>

> On Wednesday, March 13, 2013 7:53:13 AM UTC-7, śrīdṛṣṭvā wrote:

>>

>> Today is a good day)

>> Now, I feel totally free from ITRANS, because I modified itrans.cpp, 

>> itrans.h of SanDic sources.

>> It still support ITRANS, with the only exception, now I type ca-cha 

>> instead of cha-Cha. So any letter can be typed with both standards, IAST is 

>> just extension.

>> So here is sources itrans.cpp:

>> /*=========================================================================== 

>>

>>     SanDic, Sanscrit-English Dictionary 

>>     Copyright (C) 2012 Novikov Artem Gennadievich , with IAST extension 

>> by śrīdṛṣṭvā

>>

>>     This program is free software: you can redistribute it and/or modify 

>>     it under the terms of the GNU General Public License as published by 

>>     the Free Software Foundation, either version 3 of the License, or 

>>     (at your option) any later version. 

>>  

>>     This program is distributed in the hope that it will be useful, 

>>     but WITHOUT ANY WARRANTY; without even the implied warranty of 

>>     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the 

>>     GNU General Public License for more details. 

>>  

>>     You should have received a copy of the GNU General Public License 

>>     along with this program.  If not, see <http://www.gnu.org/licenses/> 

>>

>> ===========================================================================*/ 

>>  

>> #include "itrans.h" 

>>  

>> ItransDecoder::ItransDecoder() 

>> { 

>>     map[0] << ItransMapItem("aa",  "A",  QChar(0x0101),  0x0906) 

>>            << ItransMapItem("ii",  "I",   QChar(0x012b), 0x0908) 

>>            << ItransMapItem("uu",  "U",   QChar(0x016b), 0x090a) 

>>            << ItransMapItem("RRi", "R^i", QChar(0x1e5b), 0x090b) 

>>            << ItransMapItem("RRI", "R^I", QChar(0x1e5d), 0x0960) 

>>            << ItransMapItem("LLi", "L^i", QChar(0x1e37), 0x090c) 

>>            << ItransMapItem("LLI", "L^I", QChar(0x1e39), 0x0961) 

>>            << ItransMapItem("ai", 0x0910) 

>>            << ItransMapItem("au", 0x0914) 

>>            << ItransMapItem("a",  0x0905) 

>>            << ItransMapItem("i",  0x0907) 

>>            << ItransMapItem("u",  0x0909) 

>>            << ItransMapItem("e",  QChar(0x0113), 0x090f) 

>>            << ItransMapItem("o",  QChar(0x014d), 0x0913) 

>>            << ItransMapItem("M",  QChar(0x1e43), 0x0902) 

>>            << ItransMapItem("H",  QChar(0x1e25), 0x0903); 

>>     map[1] << ItransMapItem("aa",  "A",  QChar(0x0101), 0x093e) 

>>            << ItransMapItem("ii",  "I",   QChar(0x012b), 0x0940) 

>>            << ItransMapItem("uu",  "U",   QChar(0x016b), 0x0942) 

>>            << ItransMapItem("RRi", "R^i", QChar(0x1e5b), 0x0943) 

>>            << ItransMapItem("RRI", "R^I", QChar(0x1e5d), 0x0944) 

>>            << ItransMapItem("ai", 0x0948) 

>>            << ItransMapItem("au", 0x094C) 

>>            << ItransMapItem("i",  0x093f) 

>>            << ItransMapItem("u",  0x0941) 

>>            << ItransMapItem("e",  QChar(0x0113), 0x0947) 

>>            << ItransMapItem("o",  QChar(0x014d), 0x094b); 

>>     map[2] << ItransMapItem("kh", 0x0916) 

>>            << ItransMapItem("gh", 0x0918) 

>>            << ItransMapItem("~N", QChar(0x1e45), 0x0919) 

>> //           << ItransMapItem("ch", 0x091a) 

>> //           << ItransMapItem("Ch", 0x091b) 

>>            << ItransMapItem("ch", 0x091b) 

>>            << ItransMapItem("jh", 0x091d) 

>>            << ItransMapItem("~n", QChar(0x00f1), 0x091e) 

>>            << ItransMapItem("Th", QString("%1h").arg(QChar(0x1e6d)), 

>> 0x0920) 

>>            << ItransMapItem("Dh", QString("%1h").arg(QChar(0x1e0d)), 

>> 0x0922) 

>>            << ItransMapItem("th", 0x0925) 

>>            << ItransMapItem("dh", 0x0927) 

>>            << ItransMapItem("ph", 0x092b) 

>>            << ItransMapItem("bh", 0x092d) 

>>            << ItransMapItem("sh",  QChar(0x015b), 0x0936) 

>>            << ItransMapItem("Sh",  QChar(0x1e63), 0x0937) 

>>            << ItransMapItem("k",  0x0915) 

>>            << ItransMapItem("g",  0x0917) 

>>            << ItransMapItem("c",  0x091a) 

>>            << ItransMapItem("j",  0x091c) 

>>            << ItransMapItem("T",  QChar(0x1e6d), 0x091f) 

>>            << ItransMapItem("D",  QChar(0x1e0d), 0x0921) 

>>            << ItransMapItem("N",  QChar(0x1e47), 0x0923) 

>>            << ItransMapItem("t",  0x0924) 

>>            << ItransMapItem("d",  0x0926) 

>>            << ItransMapItem("n",  0x0928) 

>>            << ItransMapItem("p",  0x092a) 

>>            << ItransMapItem("b",  0x092c) 

>>            << ItransMapItem("m",  0x092e) 

>>            << ItransMapItem("y",  0x092f) 

>>            << ItransMapItem("r",  0x0930) 

>>            << ItransMapItem("l",  0x0932) 

>>            << ItransMapItem("v", "w", 0x0935) 

>>            << ItransMapItem("w",  0x0935) 

>>            << ItransMapItem("s",  0x0938) 

>>            << ItransMapItem("h",  0x0939) 

>>            << ItransMapItem("L",  0x0933); 

>>     map[3] << ItransMapItem("0",  0x0966) 

>>            << ItransMapItem("1",  0x0967) 

>>            << ItransMapItem("2",  0x0968) 

>>            << ItransMapItem("3",  0x0969) 

>>            << ItransMapItem("4",  0x096a) 

>>            << ItransMapItem("5",  0x096b) 

>>            << ItransMapItem("6",  0x096c) 

>>            << ItransMapItem("7",  0x096d) 

>>            << ItransMapItem("8",  0x096e) 

>>            << ItransMapItem("9",  0x096f); 

>> } 

>>  

>> QString ItransDecoder::decode(QString txt) 

>> { 

>>     for (int i = 0; i < map[2].count(); i++) // consonant + virama 

>>         txt.replace(QRegExp(map[2][i].txt), QString("%1%2").arg(QChar(map

>> [2][i].code), QChar(0x094d))); 

>>  

>>     for (int i = 0; i < map[1].count(); i++) // consonant - virama + 

>> vowels sign short 

>>         txt.replace(QRegExp(QString("([\\x0915-\\x0939])\\x094d%1").arg(

>> map[1][i].txt)), QString("\\1%1").arg(QChar(map[1][i].code))); 

>>  

>>     txt.replace(QRegExp("([\\x0915-\\x0939])\\x094da"), QString("\\1")); // 

>> "a" 0x0000 

>>  

>>     for (int i = 0; i < map[0].count(); i++) 

>>         txt.replace(QRegExp(map[0][i].txt), QChar(map[0][i].code)); 

>>  

>>     for (int i = 0; i < map[3].count(); i++) 

>>         txt.replace(QRegExp(map[3][i].txt), QChar(map[3][i].code)); 

>>  

>>     return txt; 

>> }

>>

>>

>>

>> The only modification of itrans.h is there-case replace of QString:

>> struct ItransMapItem

>> {

>>     ItransMapItem(QString txt, int code)

>>         : txt(REPLACE(txt)), code(code) {}

>>     ItransMapItem(QString txt1, QString txt2, int code)

>>         : txt(REPLACE(QString("(%1|%2)").arg(txt1, txt2))), code(code) {}

>>     ItransMapItem(QString txt1, QString txt2, QString txt3, int code)

>>         : txt(REPLACE(QString("(%1|%2|%3)").arg(txt1, txt2, txt3))), code

>> (code) {}

>>

>>     QString txt;

>>     int     code;

>> };

>>

>

## 4. śrīdṛṣṭvā — 2013-03-14 11:57:43

просто при попытке приаттачить файл мой браузер виснет)

шрифт у меня всегда такой был - я и не знал что должен быть какой-то 

другой, меня этот вполне устраивает)))



On Wednesday, March 13, 2013 11:13:14 PM UTC-7, Marcis wrote:

>

> Скриншоты лучше цеплять здесь, ибо сторонние ссылки имеют тенденцию 

> умирать. Что за шрифт поменяли, куда ушли от Siddhanta?

>

> среда, 13 марта 2013 г., 18:59:06 UTC+4 пользователь śrīdṛṣṭvā написал:

>>

>> Oh, forgot - screenshot

>> http://s17.postimage.org/qylwe4mgt/Screenshot_from_2013_03_13_07_43_54.png

>>

>> On Wednesday, March 13, 2013 7:53:13 AM UTC-7, śrīdṛṣṭvā wrote:

>>>

>>> Today is a good day)

>>> Now, I feel totally free from ITRANS, because I modified itrans.cpp, 

>>> itrans.h of SanDic sources.

>>> It still support ITRANS, with the only exception, now I type ca-cha 

>>> instead of cha-Cha. So any letter can be typed with both standards, IAST is 

>>> just extension.

>>> So here is sources itrans.cpp:

>>> /*=========================================================================== 

>>>

>>>     SanDic, Sanscrit-English Dictionary 

>>>     Copyright (C) 2012 Novikov Artem Gennadievich , with IAST extension 

>>> by śrīdṛṣṭvā

>>>

>>>     This program is free software: you can redistribute it and/or modify 

>>>     it under the terms of the GNU General Public License as published by 

>>>     the Free Software Foundation, either version 3 of the License, or 

>>>     (at your option) any later version. 

>>>  

>>>     This program is distributed in the hope that it will be useful, 

>>>     but WITHOUT ANY WARRANTY; without even the implied warranty of 

>>>     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the 

>>>     GNU General Public License for more details. 

>>>  

>>>     You should have received a copy of the GNU General Public License 

>>>     along with this program.  If not, see <http://www.gnu.org/licenses/> 

>>>

>>>

>>> ===========================================================================*/ 

>>>  

>>> #include "itrans.h" 

>>>  

>>> ItransDecoder::ItransDecoder() 

>>> { 

>>>     map[0] << ItransMapItem("aa",  "A",  QChar(0x0101),  0x0906) 

>>>            << ItransMapItem("ii",  "I",   QChar(0x012b), 0x0908) 

>>>            << ItransMapItem("uu",  "U",   QChar(0x016b), 0x090a) 

>>>            << ItransMapItem("RRi", "R^i", QChar(0x1e5b), 0x090b) 

>>>            << ItransMapItem("RRI", "R^I", QChar(0x1e5d), 0x0960) 

>>>            << ItransMapItem("LLi", "L^i", QChar(0x1e37), 0x090c) 

>>>            << ItransMapItem("LLI", "L^I", QChar(0x1e39), 0x0961) 

>>>            << ItransMapItem("ai", 0x0910) 

>>>            << ItransMapItem("au", 0x0914) 

>>>            << ItransMapItem("a",  0x0905) 

>>>            << ItransMapItem("i",  0x0907) 

>>>            << ItransMapItem("u",  0x0909) 

>>>            << ItransMapItem("e",  QChar(0x0113), 0x090f) 

>>>            << ItransMapItem("o",  QChar(0x014d), 0x0913) 

>>>            << ItransMapItem("M",  QChar(0x1e43), 0x0902) 

>>>            << ItransMapItem("H",  QChar(0x1e25), 0x0903); 

>>>     map[1] << ItransMapItem("aa",  "A",  QChar(0x0101), 0x093e) 

>>>            << ItransMapItem("ii",  "I",   QChar(0x012b), 0x0940) 

>>>            << ItransMapItem("uu",  "U",   QChar(0x016b), 0x0942) 

>>>            << ItransMapItem("RRi", "R^i", QChar(0x1e5b), 0x0943) 

>>>            << ItransMapItem("RRI", "R^I", QChar(0x1e5d), 0x0944) 

>>>            << ItransMapItem("ai", 0x0948) 

>>>            << ItransMapItem("au", 0x094C) 

>>>            << ItransMapItem("i",  0x093f) 

>>>            << ItransMapItem("u",  0x0941) 

>>>            << ItransMapItem("e",  QChar(0x0113), 0x0947) 

>>>            << ItransMapItem("o",  QChar(0x014d), 0x094b); 

>>>     map[2] << ItransMapItem("kh", 0x0916) 

>>>            << ItransMapItem("gh", 0x0918) 

>>>            << ItransMapItem("~N", QChar(0x1e45), 0x0919) 

>>> //           << ItransMapItem("ch", 0x091a) 

>>> //           << ItransMapItem("Ch", 0x091b) 

>>>            << ItransMapItem("ch", 0x091b) 

>>>            << ItransMapItem("jh", 0x091d) 

>>>            << ItransMapItem("~n", QChar(0x00f1), 0x091e) 

>>>            << ItransMapItem("Th", QString("%1h").arg(QChar(0x1e6d)), 

>>> 0x0920) 

>>>            << ItransMapItem("Dh", QString("%1h").arg(QChar(0x1e0d)), 

>>> 0x0922) 

>>>            << ItransMapItem("th", 0x0925) 

>>>            << ItransMapItem("dh", 0x0927) 

>>>            << ItransMapItem("ph", 0x092b) 

>>>            << ItransMapItem("bh", 0x092d) 

>>>            << ItransMapItem("sh",  QChar(0x015b), 0x0936) 

>>>            << ItransMapItem("Sh",  QChar(0x1e63), 0x0937) 

>>>            << ItransMapItem("k",  0x0915) 

>>>            << ItransMapItem("g",  0x0917) 

>>>            << ItransMapItem("c",  0x091a) 

>>>            << ItransMapItem("j",  0x091c) 

>>>            << ItransMapItem("T",  QChar(0x1e6d), 0x091f) 

>>>            << ItransMapItem("D",  QChar(0x1e0d), 0x0921) 

>>>            << ItransMapItem("N",  QChar(0x1e47), 0x0923) 

>>>            << ItransMapItem("t",  0x0924) 

>>>            << ItransMapItem("d",  0x0926) 

>>>            << ItransMapItem("n",  0x0928) 

>>>            << ItransMapItem("p",  0x092a) 

>>>            << ItransMapItem("b",  0x092c) 

>>>            << ItransMapItem("m",  0x092e) 

>>>            << ItransMapItem("y",  0x092f) 

>>>            << ItransMapItem("r",  0x0930) 

>>>            << ItransMapItem("l",  0x0932) 

>>>            << ItransMapItem("v", "w", 0x0935) 

>>>            << ItransMapItem("w",  0x0935) 

>>>            << ItransMapItem("s",  0x0938) 

>>>            << ItransMapItem("h",  0x0939) 

>>>            << ItransMapItem("L",  0x0933); 

>>>     map[3] << ItransMapItem("0",  0x0966) 

>>>            << ItransMapItem("1",  0x0967) 

>>>            << ItransMapItem("2",  0x0968) 

>>>            << ItransMapItem("3",  0x0969) 

>>>            << ItransMapItem("4",  0x096a) 

>>>            << ItransMapItem("5",  0x096b) 

>>>            << ItransMapItem("6",  0x096c) 

>>>            << ItransMapItem("7",  0x096d) 

>>>            << ItransMapItem("8",  0x096e) 

>>>            << ItransMapItem("9",  0x096f); 

>>> } 

>>>  

>>> QString ItransDecoder::decode(QString txt) 

>>> { 

>>>     for (int i = 0; i < map[2].count(); i++) // consonant + virama 

>>>         txt.replace(QRegExp(map[2][i].txt), QString("%1%2").arg(QChar(

>>> map[2][i].code), QChar(0x094d))); 

>>>  

>>>     for (int i = 0; i < map[1].count(); i++) // consonant - virama + 

>>> vowels sign short 

>>>         txt.replace(QRegExp(QString("([\\x0915-\\x0939])\\x094d%1").arg(

>>> map[1][i].txt)), QString("\\1%1").arg(QChar(map[1][i].code))); 

>>>  

>>>     txt.replace(QRegExp("([\\x0915-\\x0939])\\x094da"), QString("\\1")); // 

>>> "a" 0x0000 

>>>  

>>>     for (int i = 0; i < map[0].count(); i++) 

>>>         txt.replace(QRegExp(map[0][i].txt), QChar(map[0][i].code)); 

>>>  

>>>     for (int i = 0; i < map[3].count(); i++) 

>>>         txt.replace(QRegExp(map[3][i].txt), QChar(map[3][i].code)); 

>>>  

>>>     return txt; 

>>> }

>>>

>>>

>>>

>>> The only modification of itrans.h is there-case replace of QString:

>>> struct ItransMapItem

>>> {

>>>     ItransMapItem(QString txt, int code)

>>>         : txt(REPLACE(txt)), code(code) {}

>>>     ItransMapItem(QString txt1, QString txt2, int code)

>>>         : txt(REPLACE(QString("(%1|%2)").arg(txt1, txt2))), code(code) 

>>> {}

>>>     ItransMapItem(QString txt1, QString txt2, QString txt3, int code)

>>>         : txt(REPLACE(QString("(%1|%2|%3)").arg(txt1, txt2, txt3))),code

>>> (code) {}

>>>

>>>     QString txt;

>>>     int     code;

>>> };

>>>

>>

## 5. Artem Novikov — 2013-03-14 12:27:15

Класс!

Как дойдут руки, запилю HK, IAST, ITRANS, SLP1. Кстати, у меня там ошибка с 

регулярками, вернее с их порядком. 



среда, 13 марта 2013 г., 22:53:13 UTC+8 пользователь śrīdṛṣṭvā написал:

>

> Today is a good day)

> Now, I feel totally free from ITRANS, because I modified itrans.cpp, 

> itrans.h of SanDic sources.

> It still support ITRANS, with the only exception, now I type ca-cha 

> instead of cha-Cha. So any letter can be typed with both standards, IAST is 

> just extension.

> So here is sources itrans.cpp:

> /*=========================================================================== 

>

>     SanDic, Sanscrit-English Dictionary 

>     Copyright (C) 2012 Novikov Artem Gennadievich , with IAST extension by 

> śrīdṛṣṭvā

>

>     This program is free software: you can redistribute it and/or modify 

>     it under the terms of the GNU General Public License as published by 

>     the Free Software Foundation, either version 3 of the License, or 

>     (at your option) any later version. 

>  

>     This program is distributed in the hope that it will be useful, 

>     but WITHOUT ANY WARRANTY; without even the implied warranty of 

>     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the 

>     GNU General Public License for more details. 

>  

>     You should have received a copy of the GNU General Public License 

>     along with this program.  If not, see <http://www.gnu.org/licenses/> 

>

> ===========================================================================*/ 

>  

> #include "itrans.h" 

>  

> ItransDecoder::ItransDecoder() 

> { 

>     map[0] << ItransMapItem("aa",  "A",  QChar(0x0101),  0x0906) 

>            << ItransMapItem("ii",  "I",   QChar(0x012b), 0x0908) 

>            << ItransMapItem("uu",  "U",   QChar(0x016b), 0x090a) 

>            << ItransMapItem("RRi", "R^i", QChar(0x1e5b), 0x090b) 

>            << ItransMapItem("RRI", "R^I", QChar(0x1e5d), 0x0960) 

>            << ItransMapItem("LLi", "L^i", QChar(0x1e37), 0x090c) 

>            << ItransMapItem("LLI", "L^I", QChar(0x1e39), 0x0961) 

>            << ItransMapItem("ai", 0x0910) 

>            << ItransMapItem("au", 0x0914) 

>            << ItransMapItem("a",  0x0905) 

>            << ItransMapItem("i",  0x0907) 

>            << ItransMapItem("u",  0x0909) 

>            << ItransMapItem("e",  QChar(0x0113), 0x090f) 

>            << ItransMapItem("o",  QChar(0x014d), 0x0913) 

>            << ItransMapItem("M",  QChar(0x1e43), 0x0902) 

>            << ItransMapItem("H",  QChar(0x1e25), 0x0903); 

>     map[1] << ItransMapItem("aa",  "A",  QChar(0x0101), 0x093e) 

>            << ItransMapItem("ii",  "I",   QChar(0x012b), 0x0940) 

>            << ItransMapItem("uu",  "U",   QChar(0x016b), 0x0942) 

>            << ItransMapItem("RRi", "R^i", QChar(0x1e5b), 0x0943) 

>            << ItransMapItem("RRI", "R^I", QChar(0x1e5d), 0x0944) 

>            << ItransMapItem("ai", 0x0948) 

>            << ItransMapItem("au", 0x094C) 

>            << ItransMapItem("i",  0x093f) 

>            << ItransMapItem("u",  0x0941) 

>            << ItransMapItem("e",  QChar(0x0113), 0x0947) 

>            << ItransMapItem("o",  QChar(0x014d), 0x094b); 

>     map[2] << ItransMapItem("kh", 0x0916) 

>            << ItransMapItem("gh", 0x0918) 

>            << ItransMapItem("~N", QChar(0x1e45), 0x0919) 

> //           << ItransMapItem("ch", 0x091a) 

> //           << ItransMapItem("Ch", 0x091b) 

>            << ItransMapItem("ch", 0x091b) 

>            << ItransMapItem("jh", 0x091d) 

>            << ItransMapItem("~n", QChar(0x00f1), 0x091e) 

>            << ItransMapItem("Th", QString("%1h").arg(QChar(0x1e6d)), 

> 0x0920) 

>            << ItransMapItem("Dh", QString("%1h").arg(QChar(0x1e0d)), 

> 0x0922) 

>            << ItransMapItem("th", 0x0925) 

>            << ItransMapItem("dh", 0x0927) 

>            << ItransMapItem("ph", 0x092b) 

>            << ItransMapItem("bh", 0x092d) 

>            << ItransMapItem("sh",  QChar(0x015b), 0x0936) 

>            << ItransMapItem("Sh",  QChar(0x1e63), 0x0937) 

>            << ItransMapItem("k",  0x0915) 

>            << ItransMapItem("g",  0x0917) 

>            << ItransMapItem("c",  0x091a) 

>            << ItransMapItem("j",  0x091c) 

>            << ItransMapItem("T",  QChar(0x1e6d), 0x091f) 

>            << ItransMapItem("D",  QChar(0x1e0d), 0x0921) 

>            << ItransMapItem("N",  QChar(0x1e47), 0x0923) 

>            << ItransMapItem("t",  0x0924) 

>            << ItransMapItem("d",  0x0926) 

>            << ItransMapItem("n",  0x0928) 

>            << ItransMapItem("p",  0x092a) 

>            << ItransMapItem("b",  0x092c) 

>            << ItransMapItem("m",  0x092e) 

>            << ItransMapItem("y",  0x092f) 

>            << ItransMapItem("r",  0x0930) 

>            << ItransMapItem("l",  0x0932) 

>            << ItransMapItem("v", "w", 0x0935) 

>            << ItransMapItem("w",  0x0935) 

>            << ItransMapItem("s",  0x0938) 

>            << ItransMapItem("h",  0x0939) 

>            << ItransMapItem("L",  0x0933); 

>     map[3] << ItransMapItem("0",  0x0966) 

>            << ItransMapItem("1",  0x0967) 

>            << ItransMapItem("2",  0x0968) 

>            << ItransMapItem("3",  0x0969) 

>            << ItransMapItem("4",  0x096a) 

>            << ItransMapItem("5",  0x096b) 

>            << ItransMapItem("6",  0x096c) 

>            << ItransMapItem("7",  0x096d) 

>            << ItransMapItem("8",  0x096e) 

>            << ItransMapItem("9",  0x096f); 

> } 

>  

> QString ItransDecoder::decode(QString txt) 

> { 

>     for (int i = 0; i < map[2].count(); i++) // consonant + virama 

>         txt.replace(QRegExp(map[2][i].txt), QString("%1%2").arg(QChar(map[

> 2][i].code), QChar(0x094d))); 

>  

>     for (int i = 0; i < map[1].count(); i++) // consonant - virama + 

> vowels sign short 

>         txt.replace(QRegExp(QString("([\\x0915-\\x0939])\\x094d%1").arg(

> map[1][i].txt)), QString("\\1%1").arg(QChar(map[1][i].code))); 

>  

>     txt.replace(QRegExp("([\\x0915-\\x0939])\\x094da"), QString("\\1")); // 

> "a" 0x0000 

>  

>     for (int i = 0; i < map[0].count(); i++) 

>         txt.replace(QRegExp(map[0][i].txt), QChar(map[0][i].code)); 

>  

>     for (int i = 0; i < map[3].count(); i++) 

>         txt.replace(QRegExp(map[3][i].txt), QChar(map[3][i].code)); 

>  

>     return txt; 

> }

>

>

>

> The only modification of itrans.h is there-case replace of QString:

> struct ItransMapItem

> {

>     ItransMapItem(QString txt, int code)

>         : txt(REPLACE(txt)), code(code) {}

>     ItransMapItem(QString txt1, QString txt2, int code)

>         : txt(REPLACE(QString("(%1|%2)").arg(txt1, txt2))), code(code) {}

>     ItransMapItem(QString txt1, QString txt2, QString txt3, int code)

>         : txt(REPLACE(QString("(%1|%2|%3)").arg(txt1, txt2, txt3))), code(

> code) {}

>

>     QString txt;

>     int     code;

> };

>

## 6. śrīdṛṣṭvā — 2013-03-15 13:08:36

Вот сейчас посмотрел шрифт. На скриншоте Siddhanta-calcutta.ttf

Еще, кому интересен быстрый удобный ввод, то я нашел оптимальное *(для себя)

* решение. Итак, система у меня Ubuntu 12.04LTS, но думаю на любой *nix 

должно стать без проблем. Я не пробовал с исходников ставить, но подозреваю 

что возможно даже станет на мак. Устанавливаем вот такой пакетик:

apt-get install ibus-m17n*

*

*Открываем system tools->system settings->language support->input method*, 

по умолчанию *none* назначаем *ibus*. Возможно прийдется ребутнуться, потом 

открываем *system tools->preferences->keyboatd input methods*, вкладка *input 

methods*, добавляем *sanskrit*, там есть два варианта - первый это набор 

транслитерации IAST, второй вариант - деванагари методом harvard-kyoto. Он 

похож на ITRANS, но я считаю он удобнее, в основном за удобство ввода 

символов типа ङ ञ ऋ.

После подключения такого input method вводить деванагари можно куда угодно, 

даже в консоль, правда там она парсится плохенько. Скорость такого набора 

очень радует.





On Wednesday, March 13, 2013 11:13:14 PM UTC-7, Marcis wrote:

>

> Скриншоты лучше цеплять здесь, ибо сторонние ссылки имеют тенденцию 

> умирать. Что за шрифт поменяли, куда ушли от Siddhanta?

>

> среда, 13 марта 2013 г., 18:59:06 UTC+4 пользователь śrīdṛṣṭvā написал:

>>

>> Oh, forgot - screenshot

>> http://s17.postimage.org/qylwe4mgt/Screenshot_from_2013_03_13_07_43_54.png

>>

>> On Wednesday, March 13, 2013 7:53:13 AM UTC-7, śrīdṛṣṭvā wrote:

>>>

>>> Today is a good day)

>>> Now, I feel totally free from ITRANS, because I modified itrans.cpp, 

>>> itrans.h of SanDic sources.

>>> It still support ITRANS, with the only exception, now I type ca-cha 

>>> instead of cha-Cha. So any letter can be typed with both standards, IAST is 

>>> just extension.

>>> So here is sources itrans.cpp:

>>> /*=========================================================================== 

>>>

>>>     SanDic, Sanscrit-English Dictionary 

>>>     Copyright (C) 2012 Novikov Artem Gennadievich , with IAST extension 

>>> by śrīdṛṣṭvā

>>>

>>>     This program is free software: you can redistribute it and/or modify 

>>>     it under the terms of the GNU General Public License as published by 

>>>     the Free Software Foundation, either version 3 of the License, or 

>>>     (at your option) any later version. 

>>>  

>>>     This program is distributed in the hope that it will be useful, 

>>>     but WITHOUT ANY WARRANTY; without even the implied warranty of 

>>>     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the 

>>>     GNU General Public License for more details. 

>>>  

>>>     You should have received a copy of the GNU General Public License 

>>>     along with this program.  If not, see <http://www.gnu.org/licenses/> 

>>>

>>>

>>> ===========================================================================*/ 

>>>  

>>> #include "itrans.h" 

>>>  

>>> ItransDecoder::ItransDecoder() 

>>> { 

>>>     map[0] << ItransMapItem("aa",  "A",  QChar(0x0101),  0x0906) 

>>>            << ItransMapItem("ii",  "I",   QChar(0x012b), 0x0908) 

>>>            << ItransMapItem("uu",  "U",   QChar(0x016b), 0x090a) 

>>>            << ItransMapItem("RRi", "R^i", QChar(0x1e5b), 0x090b) 

>>>            << ItransMapItem("RRI", "R^I", QChar(0x1e5d), 0x0960) 

>>>            << ItransMapItem("LLi", "L^i", QChar(0x1e37), 0x090c) 

>>>            << ItransMapItem("LLI", "L^I", QChar(0x1e39), 0x0961) 

>>>            << ItransMapItem("ai", 0x0910) 

>>>            << ItransMapItem("au", 0x0914) 

>>>            << ItransMapItem("a",  0x0905) 

>>>            << ItransMapItem("i",  0x0907) 

>>>            << ItransMapItem("u",  0x0909) 

>>>            << ItransMapItem("e",  QChar(0x0113), 0x090f) 

>>>            << ItransMapItem("o",  QChar(0x014d), 0x0913) 

>>>            << ItransMapItem("M",  QChar(0x1e43), 0x0902) 

>>>            << ItransMapItem("H",  QChar(0x1e25), 0x0903); 

>>>     map[1] << ItransMapItem("aa",  "A",  QChar(0x0101), 0x093e) 

>>>            << ItransMapItem("ii",  "I",   QChar(0x012b), 0x0940) 

>>>            << ItransMapItem("uu",  "U",   QChar(0x016b), 0x0942) 

>>>            << ItransMapItem("RRi", "R^i", QChar(0x1e5b), 0x0943) 

>>>            << ItransMapItem("RRI", "R^I", QChar(0x1e5d), 0x0944) 

>>>            << ItransMapItem("ai", 0x0948) 

>>>            << ItransMapItem("au", 0x094C) 

>>>            << ItransMapItem("i",  0x093f) 

>>>            << ItransMapItem("u",  0x0941) 

>>>            << ItransMapItem("e",  QChar(0x0113), 0x0947) 

>>>            << ItransMapItem("o",  QChar(0x014d), 0x094b); 

>>>     map[2] << ItransMapItem("kh", 0x0916) 

>>>            << ItransMapItem("gh", 0x0918) 

>>>            << ItransMapItem("~N", QChar(0x1e45), 0x0919) 

>>> //           << ItransMapItem("ch", 0x091a) 

>>> //           << ItransMapItem("Ch", 0x091b) 

>>>            << ItransMapItem("ch", 0x091b) 

>>>            << ItransMapItem("jh", 0x091d) 

>>>            << ItransMapItem("~n", QChar(0x00f1), 0x091e) 

>>>            << ItransMapItem("Th", QString("%1h").arg(QChar(0x1e6d)), 

>>> 0x0920) 

>>>            << ItransMapItem("Dh", QString("%1h").arg(QChar(0x1e0d)), 

>>> 0x0922) 

>>>            << ItransMapItem("th", 0x0925) 

>>>            << ItransMapItem("dh", 0x0927) 

>>>            << ItransMapItem("ph", 0x092b) 

>>>            << ItransMapItem("bh", 0x092d) 

>>>            << ItransMapItem("sh",  QChar(0x015b), 0x0936) 

>>>            << ItransMapItem("Sh",  QChar(0x1e63), 0x0937) 

>>>            << ItransMapItem("k",  0x0915) 

>>>            << ItransMapItem("g",  0x0917) 

>>>            << ItransMapItem("c",  0x091a) 

>>>            << ItransMapItem("j",  0x091c) 

>>>            << ItransMapItem("T",  QChar(0x1e6d), 0x091f) 

>>>            << ItransMapItem("D",  QChar(0x1e0d), 0x0921) 

>>>            << ItransMapItem("N",  QChar(0x1e47), 0x0923) 

>>>            << ItransMapItem("t",  0x0924) 

>>>            << ItransMapItem("d",  0x0926) 

>>>            << ItransMapItem("n",  0x0928) 

>>>            << ItransMapItem("p",  0x092a) 

>>>            << ItransMapItem("b",  0x092c) 

>>>            << ItransMapItem("m",  0x092e) 

>>>            << ItransMapItem("y",  0x092f) 

>>>            << ItransMapItem("r",  0x0930) 

>>>            << ItransMapItem("l",  0x0932) 

>>>            << ItransMapItem("v", "w", 0x0935) 

>>>            << ItransMapItem("w",  0x0935) 

>>>            << ItransMapItem("s",  0x0938) 

>>>            << ItransMapItem("h",  0x0939) 

>>>            << ItransMapItem("L",  0x0933); 

>>>     map[3] << ItransMapItem("0",  0x0966) 

>>>            << ItransMapItem("1",  0x0967) 

>>>            << ItransMapItem("2",  0x0968) 

>>>            << ItransMapItem("3",  0x0969) 

>>>            << ItransMapItem("4",  0x096a) 

>>>            << ItransMapItem("5",  0x096b) 

>>>            << ItransMapItem("6",  0x096c) 

>>>            << ItransMapItem("7",  0x096d) 

>>>            << ItransMapItem("8",  0x096e) 

>>>            << ItransMapItem("9",  0x096f); 

>>> } 

>>>  

>>> QString ItransDecoder::decode(QString txt) 

>>> { 

>>>     for (int i = 0; i < map[2].count(); i++) // consonant + virama 

>>>         txt.replace(QRegExp(map[2][i].txt), QString("%1%2").arg(QChar(

>>> map[2][i].code), QChar(0x094d))); 

>>>  

>>>     for (int i = 0; i < map[1].count(); i++) // consonant - virama + 

>>> vowels sign short 

>>>         txt.replace(QRegExp(QString("([\\x0915-\\x0939])\\x094d%1").arg(

>>> map[1][i].txt)), QString("\\1%1").arg(QChar(map[1][i].code))); 

>>>  

>>>     txt.replace(QRegExp("([\\x0915-\\x0939])\\x094da"), QString("\\1")); // 

>>> "a" 0x0000 

>>>  

>>>     for (int i = 0; i < map[0].count(); i++) 

>>>         txt.replace(QRegExp(map[0][i].txt), QChar(map[0][i].code)); 

>>>  

>>>     for (int i = 0; i < map[3].count(); i++) 

>>>         txt.replace(QRegExp(map[3][i].txt), QChar(map[3][i].code)); 

>>>  

>>>     return txt; 

>>> }

>>>

>>>

>>>

>>> The only modification of itrans.h is there-case replace of QString:

>>> struct ItransMapItem

>>> {

>>>     ItransMapItem(QString txt, int code)

>>>         : txt(REPLACE(txt)), code(code) {}

>>>     ItransMapItem(QString txt1, QString txt2, int code)

>>>         : txt(REPLACE(QString("(%1|%2)").arg(txt1, txt2))), code(code) 

>>> {}

>>>     ItransMapItem(QString txt1, QString txt2, QString txt3, int code)

>>>         : txt(REPLACE(QString("(%1|%2|%3)").arg(txt1, txt2, txt3))),code

>>> (code) {}

>>>

>>>     QString txt;

>>>     int     code;

>>> };

>>>

>>

## 7. Artem Novikov — 2013-03-15 14:07:41

Что за шрифт поменяли, куда ушли от Siddhanta? Щас он уйдет...

Siddhanta зашит в оболочку и жестко прописан, было бы странно если бы на 

скрине был другой шрифт.



четверг, 14 марта 2013 г., 14:13:14 UTC+8 пользователь Marcis написал:

>

> Скриншоты лучше цеплять здесь, ибо сторонние ссылки имеют тенденцию 

> умирать. Что за шрифт поменяли, куда ушли от Siddhanta?

>

> среда, 13 марта 2013 г., 18:59:06 UTC+4 пользователь śrīdṛṣṭvā написал:

>>

>> Oh, forgot - screenshot

>> http://s17.postimage.org/qylwe4mgt/Screenshot_from_2013_03_13_07_43_54.png

>>

>> On Wednesday, March 13, 2013 7:53:13 AM UTC-7, śrīdṛṣṭvā wrote:

>>>

>>> Today is a good day)

>>> Now, I feel totally free from ITRANS, because I modified itrans.cpp, 

>>> itrans.h of SanDic sources.

>>> It still support ITRANS, with the only exception, now I type ca-cha 

>>> instead of cha-Cha. So any letter can be typed with both standards, IAST is 

>>> just extension.

>>> So here is sources itrans.cpp:

>>> /*=========================================================================== 

>>>

>>>     SanDic, Sanscrit-English Dictionary 

>>>     Copyright (C) 2012 Novikov Artem Gennadievich , with IAST extension 

>>> by śrīdṛṣṭvā

>>>

>>>     This program is free software: you can redistribute it and/or modify 

>>>     it under the terms of the GNU General Public License as published by 

>>>     the Free Software Foundation, either version 3 of the License, or 

>>>     (at your option) any later version. 

>>>  

>>>     This program is distributed in the hope that it will be useful, 

>>>     but WITHOUT ANY WARRANTY; without even the implied warranty of 

>>>     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the 

>>>     GNU General Public License for more details. 

>>>  

>>>     You should have received a copy of the GNU General Public License 

>>>     along with this program.  If not, see <http://www.gnu.org/licenses/> 

>>>

>>>

>>> ===========================================================================*/ 

>>>  

>>> #include "itrans.h" 

>>>  

>>> ItransDecoder::ItransDecoder() 

>>> { 

>>>     map[0] << ItransMapItem("aa",  "A",  QChar(0x0101),  0x0906) 

>>>            << ItransMapItem("ii",  "I",   QChar(0x012b), 0x0908) 

>>>            << ItransMapItem("uu",  "U",   QChar(0x016b), 0x090a) 

>>>            << ItransMapItem("RRi", "R^i", QChar(0x1e5b), 0x090b) 

>>>            << ItransMapItem("RRI", "R^I", QChar(0x1e5d), 0x0960) 

>>>            << ItransMapItem("LLi", "L^i", QChar(0x1e37), 0x090c) 

>>>            << ItransMapItem("LLI", "L^I", QChar(0x1e39), 0x0961) 

>>>            << ItransMapItem("ai", 0x0910) 

>>>            << ItransMapItem("au", 0x0914) 

>>>            << ItransMapItem("a",  0x0905) 

>>>            << ItransMapItem("i",  0x0907) 

>>>            << ItransMapItem("u",  0x0909) 

>>>            << ItransMapItem("e",  QChar(0x0113), 0x090f) 

>>>            << ItransMapItem("o",  QChar(0x014d), 0x0913) 

>>>            << ItransMapItem("M",  QChar(0x1e43), 0x0902) 

>>>            << ItransMapItem("H",  QChar(0x1e25), 0x0903); 

>>>     map[1] << ItransMapItem("aa",  "A",  QChar(0x0101), 0x093e) 

>>>            << ItransMapItem("ii",  "I",   QChar(0x012b), 0x0940) 

>>>            << ItransMapItem("uu",  "U",   QChar(0x016b), 0x0942) 

>>>            << ItransMapItem("RRi", "R^i", QChar(0x1e5b), 0x0943) 

>>>            << ItransMapItem("RRI", "R^I", QChar(0x1e5d), 0x0944) 

>>>            << ItransMapItem("ai", 0x0948) 

>>>            << ItransMapItem("au", 0x094C) 

>>>            << ItransMapItem("i",  0x093f) 

>>>            << ItransMapItem("u",  0x0941) 

>>>            << ItransMapItem("e",  QChar(0x0113), 0x0947) 

>>>            << ItransMapItem("o",  QChar(0x014d), 0x094b); 

>>>     map[2] << ItransMapItem("kh", 0x0916) 

>>>            << ItransMapItem("gh", 0x0918) 

>>>            << ItransMapItem("~N", QChar(0x1e45), 0x0919) 

>>> //           << ItransMapItem("ch", 0x091a) 

>>> //           << ItransMapItem("Ch", 0x091b) 

>>>            << ItransMapItem("ch", 0x091b) 

>>>            << ItransMapItem("jh", 0x091d) 

>>>            << ItransMapItem("~n", QChar(0x00f1), 0x091e) 

>>>            << ItransMapItem("Th", QString("%1h").arg(QChar(0x1e6d)), 

>>> 0x0920) 

>>>            << ItransMapItem("Dh", QString("%1h").arg(QChar(0x1e0d)), 

>>> 0x0922) 

>>>            << ItransMapItem("th", 0x0925) 

>>>            << ItransMapItem("dh", 0x0927) 

>>>            << ItransMapItem("ph", 0x092b) 

>>>            << ItransMapItem("bh", 0x092d) 

>>>            << ItransMapItem("sh",  QChar(0x015b), 0x0936) 

>>>            << ItransMapItem("Sh",  QChar(0x1e63), 0x0937) 

>>>            << ItransMapItem("k",  0x0915) 

>>>            << ItransMapItem("g",  0x0917) 

>>>            << ItransMapItem("c",  0x091a) 

>>>            << ItransMapItem("j",  0x091c) 

>>>            << ItransMapItem("T",  QChar(0x1e6d), 0x091f) 

>>>            << ItransMapItem("D",  QChar(0x1e0d), 0x0921) 

>>>            << ItransMapItem("N",  QChar(0x1e47), 0x0923) 

>>>            << ItransMapItem("t",  0x0924) 

>>>            << ItransMapItem("d",  0x0926) 

>>>            << ItransMapItem("n",  0x0928) 

>>>            << ItransMapItem("p",  0x092a) 

>>>            << ItransMapItem("b",  0x092c) 

>>>            << ItransMapItem("m",  0x092e) 

>>>            << ItransMapItem("y",  0x092f) 

>>>            << ItransMapItem("r",  0x0930) 

>>>            << ItransMapItem("l",  0x0932) 

>>>            << ItransMapItem("v", "w", 0x0935) 

>>>            << ItransMapItem("w",  0x0935) 

>>>            << ItransMapItem("s",  0x0938) 

>>>            << ItransMapItem("h",  0x0939) 

>>>            << ItransMapItem("L",  0x0933); 

>>>     map[3] << ItransMapItem("0",  0x0966) 

>>>            << ItransMapItem("1",  0x0967) 

>>>            << ItransMapItem("2",  0x0968) 

>>>            << ItransMapItem("3",  0x0969) 

>>>            << ItransMapItem("4",  0x096a) 

>>>            << ItransMapItem("5",  0x096b) 

>>>            << ItransMapItem("6",  0x096c) 

>>>            << ItransMapItem("7",  0x096d) 

>>>            << ItransMapItem("8",  0x096e) 

>>>            << ItransMapItem("9",  0x096f); 

>>> } 

>>>  

>>> QString ItransDecoder::decode(QString txt) 

>>> { 

>>>     for (int i = 0; i < map[2].count(); i++) // consonant + virama 

>>>         txt.replace(QRegExp(map[2][i].txt), QString("%1%2").arg(QChar(

>>> map[2][i].code), QChar(0x094d))); 

>>>  

>>>     for (int i = 0; i < map[1].count(); i++) // consonant - virama + 

>>> vowels sign short 

>>>         txt.replace(QRegExp(QString("([\\x0915-\\x0939])\\x094d%1").arg(

>>> map[1][i].txt)), QString("\\1%1").arg(QChar(map[1][i].code))); 

>>>  

>>>     txt.replace(QRegExp("([\\x0915-\\x0939])\\x094da"), QString("\\1")); // 

>>> "a" 0x0000 

>>>  

>>>     for (int i = 0; i < map[0].count(); i++) 

>>>         txt.replace(QRegExp(map[0][i].txt), QChar(map[0][i].code)); 

>>>  

>>>     for (int i = 0; i < map[3].count(); i++) 

>>>         txt.replace(QRegExp(map[3][i].txt), QChar(map[3][i].code)); 

>>>  

>>>     return txt; 

>>> }

>>>

>>>

>>>

>>> The only modification of itrans.h is there-case replace of QString:

>>> struct ItransMapItem

>>> {

>>>     ItransMapItem(QString txt, int code)

>>>         : txt(REPLACE(txt)), code(code) {}

>>>     ItransMapItem(QString txt1, QString txt2, int code)

>>>         : txt(REPLACE(QString("(%1|%2)").arg(txt1, txt2))), code(code) 

>>> {}

>>>     ItransMapItem(QString txt1, QString txt2, QString txt3, int code)

>>>         : txt(REPLACE(QString("(%1|%2|%3)").arg(txt1, txt2, txt3))),code

>>> (code) {}

>>>

>>>     QString txt;

>>>     int     code;

>>> };

>>>

>>

## 8. śrīdṛṣṭvā — 2013-03-18 18:28:22

Ну, компьютеры они как люди — у каждого свои странности...

http://s11.postimage.org/xwf9kq5e9/Screenshot_from_2013_03_18_08_00_23.png

http://s24.postimage.org/pm160sdv7/Screenshot_from_2013_03_18_08_14_38.png

http://s10.postimage.org/binohimh3/Screenshot_from_2013_03_18_08_27_25.png



On Friday, March 15, 2013 4:07:41 AM UTC-7, Artem Novikov wrote:

>

> Что за шрифт поменяли, куда ушли от Siddhanta? Щас он уйдет...

> Siddhanta зашит в оболочку и жестко прописан, было бы странно если бы на 

> скрине был другой шрифт.

>

> четверг, 14 марта 2013 г., 14:13:14 UTC+8 пользователь Marcis написал:

>>

>> Скриншоты лучше цеплять здесь, ибо сторонние ссылки имеют тенденцию 

>> умирать. Что за шрифт поменяли, куда ушли от Siddhanta?

>>

>> среда, 13 марта 2013 г., 18:59:06 UTC+4 пользователь śrīdṛṣṭvā написал:

>>>

>>> Oh, forgot - screenshot

>>>

>>> http://s17.postimage.org/qylwe4mgt/Screenshot_from_2013_03_13_07_43_54.png

>>>

>>> On Wednesday, March 13, 2013 7:53:13 AM UTC-7, śrīdṛṣṭvā wrote:

>>>>

>>>> Today is a good day)

>>>> Now, I feel totally free from ITRANS, because I modified itrans.cpp, 

>>>> itrans.h of SanDic sources.

>>>> It still support ITRANS, with the only exception, now I type ca-cha 

>>>> instead of cha-Cha. So any letter can be typed with both standards, IAST is 

>>>> just extension.

>>>> So here is sources itrans.cpp:

>>>> /*=========================================================================== 

>>>>

>>>>     SanDic, Sanscrit-English Dictionary 

>>>>     Copyright (C) 2012 Novikov Artem Gennadievich , with IAST extension 

>>>> by śrīdṛṣṭvā

>>>>

>>>>     This program is free software: you can redistribute it and/or 

>>>> modify 

>>>>     it under the terms of the GNU General Public License as published 

>>>> by 

>>>>     the Free Software Foundation, either version 3 of the License, or 

>>>>     (at your option) any later version. 

>>>>  

>>>>     This program is distributed in the hope that it will be useful, 

>>>>     but WITHOUT ANY WARRANTY; without even the implied warranty of 

>>>>     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the 

>>>>     GNU General Public License for more details. 

>>>>  

>>>>     You should have received a copy of the GNU General Public License 

>>>>     along with this program.  If not, see <http://www.gnu.org/licenses/> 

>>>>

>>>>

>>>> ===========================================================================*/ 

>>>>  

>>>> #include "itrans.h" 

>>>>  

>>>> ItransDecoder::ItransDecoder() 

>>>> { 

>>>>     map[0] << ItransMapItem("aa",  "A",  QChar(0x0101),  0x0906) 

>>>>            << ItransMapItem("ii",  "I",   QChar(0x012b), 0x0908) 

>>>>            << ItransMapItem("uu",  "U",   QChar(0x016b), 0x090a) 

>>>>            << ItransMapItem("RRi", "R^i", QChar(0x1e5b), 0x090b) 

>>>>            << ItransMapItem("RRI", "R^I", QChar(0x1e5d), 0x0960) 

>>>>            << ItransMapItem("LLi", "L^i", QChar(0x1e37), 0x090c) 

>>>>            << ItransMapItem("LLI", "L^I", QChar(0x1e39), 0x0961) 

>>>>            << ItransMapItem("ai", 0x0910) 

>>>>            << ItransMapItem("au", 0x0914) 

>>>>            << ItransMapItem("a",  0x0905) 

>>>>            << ItransMapItem("i",  0x0907) 

>>>>            << ItransMapItem("u",  0x0909) 

>>>>            << ItransMapItem("e",  QChar(0x0113), 0x090f) 

>>>>            << ItransMapItem("o",  QChar(0x014d), 0x0913) 

>>>>            << ItransMapItem("M",  QChar(0x1e43), 0x0902) 

>>>>            << ItransMapItem("H",  QChar(0x1e25), 0x0903); 

>>>>     map[1] << ItransMapItem("aa",  "A",  QChar(0x0101), 0x093e) 

>>>>            << ItransMapItem("ii",  "I",   QChar(0x012b), 0x0940) 

>>>>            << ItransMapItem("uu",  "U",   QChar(0x016b), 0x0942) 

>>>>            << ItransMapItem("RRi", "R^i", QChar(0x1e5b), 0x0943) 

>>>>            << ItransMapItem("RRI", "R^I", QChar(0x1e5d), 0x0944) 

>>>>            << ItransMapItem("ai", 0x0948) 

>>>>            << ItransMapItem("au", 0x094C) 

>>>>            << ItransMapItem("i",  0x093f) 

>>>>            << ItransMapItem("u",  0x0941) 

>>>>            << ItransMapItem("e",  QChar(0x0113), 0x0947) 

>>>>            << ItransMapItem("o",  QChar(0x014d), 0x094b); 

>>>>     map[2] << ItransMapItem("kh", 0x0916) 

>>>>            << ItransMapItem("gh", 0x0918) 

>>>>            << ItransMapItem("~N", QChar(0x1e45), 0x0919) 

>>>> //           << ItransMapItem("ch", 0x091a) 

>>>> //           << ItransMapItem("Ch", 0x091b) 

>>>>            << ItransMapItem("ch", 0x091b) 

>>>>            << ItransMapItem("jh", 0x091d) 

>>>>            << ItransMapItem("~n", QChar(0x00f1), 0x091e) 

>>>>            << ItransMapItem("Th", QString("%1h").arg(QChar(0x1e6d)), 

>>>> 0x0920) 

>>>>            << ItransMapItem("Dh", QString("%1h").arg(QChar(0x1e0d)), 

>>>> 0x0922) 

>>>>            << ItransMapItem("th", 0x0925) 

>>>>            << ItransMapItem("dh", 0x0927) 

>>>>            << ItransMapItem("ph", 0x092b) 

>>>>            << ItransMapItem("bh", 0x092d) 

>>>>            << ItransMapItem("sh",  QChar(0x015b), 0x0936) 

>>>>            << ItransMapItem("Sh",  QChar(0x1e63), 0x0937) 

>>>>            << ItransMapItem("k",  0x0915) 

>>>>            << ItransMapItem("g",  0x0917) 

>>>>            << ItransMapItem("c",  0x091a) 

>>>>            << ItransMapItem("j",  0x091c) 

>>>>            << ItransMapItem("T",  QChar(0x1e6d), 0x091f) 

>>>>            << ItransMapItem("D",  QChar(0x1e0d), 0x0921) 

>>>>            << ItransMapItem("N",  QChar(0x1e47), 0x0923) 

>>>>            << ItransMapItem("t",  0x0924) 

>>>>            << ItransMapItem("d",  0x0926) 

>>>>            << ItransMapItem("n",  0x0928) 

>>>>            << ItransMapItem("p",  0x092a) 

>>>>            << ItransMapItem("b",  0x092c) 

>>>>            << ItransMapItem("m",  0x092e) 

>>>>            << ItransMapItem("y",  0x092f) 

>>>>            << ItransMapItem("r",  0x0930) 

>>>>            << ItransMapItem("l",  0x0932) 

>>>>            << ItransMapItem("v", "w", 0x0935) 

>>>>            << ItransMapItem("w",  0x0935) 

>>>>            << ItransMapItem("s",  0x0938) 

>>>>            << ItransMapItem("h",  0x0939) 

>>>>            << ItransMapItem("L",  0x0933); 

>>>>     map[3] << ItransMapItem("0",  0x0966) 

>>>>            << ItransMapItem("1",  0x0967) 

>>>>            << ItransMapItem("2",  0x0968) 

>>>>            << ItransMapItem("3",  0x0969) 

>>>>            << ItransMapItem("4",  0x096a) 

>>>>            << ItransMapItem("5",  0x096b) 

>>>>            << ItransMapItem("6",  0x096c) 

>>>>            << ItransMapItem("7",  0x096d) 

>>>>            << ItransMapItem("8",  0x096e) 

>>>>            << ItransMapItem("9",  0x096f); 

>>>> } 

>>>>  

>>>> QString ItransDecoder::decode(QString txt) 

>>>> { 

>>>>     for (int i = 0; i < map[2].count(); i++) // consonant + virama 

>>>>         txt.replace(QRegExp(map[2][i].txt), QString("%1%2").arg(QChar(

>>>> map[2][i].code), QChar(0x094d))); 

>>>>  

>>>>     for (int i = 0; i < map[1].count(); i++) // consonant - virama + 

>>>> vowels sign short 

>>>>         txt.replace(QRegExp(QString("([\\x0915-\\x0939])\\x094d%1").arg

>>>> (map[1][i].txt)), QString("\\1%1").arg(QChar(map[1][i].code))); 

>>>>  

>>>>     txt.replace(QRegExp("([\\x0915-\\x0939])\\x094da"), QString("\\1"

>>>> )); // "a" 0x0000 

>>>>  

>>>>     for (int i = 0; i < map[0].count(); i++) 

>>>>         txt.replace(QRegExp(map[0][i].txt), QChar(map[0][i].code)); 

>>>>  

>>>>     for (int i = 0; i < map[3].count(); i++) 

>>>>         txt.replace(QRegExp(map[3][i].txt), QChar(map[3][i].code)); 

>>>>  

>>>>     return txt; 

>>>> }

>>>>

>>>>

>>>>

>>>> The only modification of itrans.h is there-case replace of QString:

>>>> struct ItransMapItem

>>>> {

>>>>     ItransMapItem(QString txt, int code)

>>>>         : txt(REPLACE(txt)), code(code) {}

>>>>     ItransMapItem(QString txt1, QString txt2, int code)

>>>>         : txt(REPLACE(QString("(%1|%2)").arg(txt1, txt2))), code(code) 

>>>> {}

>>>>     ItransMapItem(QString txt1, QString txt2, QString txt3, int code)

>>>>         : txt(REPLACE(QString("(%1|%2|%3)").arg(txt1, txt2, txt3))),code

>>>> (code) {}

>>>>

>>>>     QString txt;

>>>>     int     code;

>>>> };

>>>>

>>>

## 9. Artem Novikov — 2013-03-18 19:06:15

Почему то считал, что шрифт не переопределить. 

Хотя, если стиль меняется 

myapp -stylesheet=stylesheet.qss

то оказывается можно. Можете скрин заголовка окна карточки выложить (там 

шрифт системный и программно не меняется)?



понедельник, 18 марта 2013 г., 23:28:22 UTC+8 пользователь śrīdṛṣṭvā 

написал:

>

> Ну, компьютеры они как люди — у каждого свои странности...

> http://s11.postimage.org/xwf9kq5e9/Screenshot_from_2013_03_18_08_00_23.png

> http://s24.postimage.org/pm160sdv7/Screenshot_from_2013_03_18_08_14_38.png

> http://s10.postimage.org/binohimh3/Screenshot_from_2013_03_18_08_27_25.png

>

> On Friday, March 15, 2013 4:07:41 AM UTC-7, Artem Novikov wrote:

>>

>> Что за шрифт поменяли, куда ушли от Siddhanta? Щас он уйдет...

>> Siddhanta зашит в оболочку и жестко прописан, было бы странно если бы на 

>> скрине был другой шрифт.

>>

>> четверг, 14 марта 2013 г., 14:13:14 UTC+8 пользователь Marcis написал:

>>>

>>> Скриншоты лучше цеплять здесь, ибо сторонние ссылки имеют тенденцию 

>>> умирать. Что за шрифт поменяли, куда ушли от Siddhanta?

>>>

>>> среда, 13 марта 2013 г., 18:59:06 UTC+4 пользователь śrīdṛṣṭvā написал:

>>>>

>>>> Oh, forgot - screenshot

>>>>

>>>> http://s17.postimage.org/qylwe4mgt/Screenshot_from_2013_03_13_07_43_54.png

>>>>

>>>> On Wednesday, March 13, 2013 7:53:13 AM UTC-7, śrīdṛṣṭvā wrote:

>>>>>

>>>>> Today is a good day)

>>>>> Now, I feel totally free from ITRANS, because I modified itrans.cpp, 

>>>>> itrans.h of SanDic sources.

>>>>> It still support ITRANS, with the only exception, now I type ca-cha 

>>>>> instead of cha-Cha. So any letter can be typed with both standards, IAST is 

>>>>> just extension.

>>>>> So here is sources itrans.cpp:

>>>>> /*=========================================================================== 

>>>>>

>>>>>     SanDic, Sanscrit-English Dictionary 

>>>>>     Copyright (C) 2012 Novikov Artem Gennadievich , with IAST 

>>>>> extension by śrīdṛṣṭvā

>>>>>

>>>>>     This program is free software: you can redistribute it and/or 

>>>>> modify 

>>>>>     it under the terms of the GNU General Public License as published 

>>>>> by 

>>>>>     the Free Software Foundation, either version 3 of the License, or 

>>>>>     (at your option) any later version. 

>>>>>  

>>>>>     This program is distributed in the hope that it will be useful, 

>>>>>     but WITHOUT ANY WARRANTY; without even the implied warranty of 

>>>>>     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the 

>>>>>     GNU General Public License for more details. 

>>>>>  

>>>>>     You should have received a copy of the GNU General Public License 

>>>>>     along with this program.  If not, see <

>>>>> http://www.gnu.org/licenses/> 

>>>>>

>>>>> ===========================================================================*/ 

>>>>>  

>>>>> #include "itrans.h" 

>>>>>  

>>>>> ItransDecoder::ItransDecoder() 

>>>>> { 

>>>>>     map[0] << ItransMapItem("aa",  "A",  QChar(0x0101),  0x0906) 

>>>>>            << ItransMapItem("ii",  "I",   QChar(0x012b), 0x0908) 

>>>>>            << ItransMapItem("uu",  "U",   QChar(0x016b), 0x090a) 

>>>>>            << ItransMapItem("RRi", "R^i", QChar(0x1e5b), 0x090b) 

>>>>>            << ItransMapItem("RRI", "R^I", QChar(0x1e5d), 0x0960) 

>>>>>            << ItransMapItem("LLi", "L^i", QChar(0x1e37), 0x090c) 

>>>>>            << ItransMapItem("LLI", "L^I", QChar(0x1e39), 0x0961) 

>>>>>            << ItransMapItem("ai", 0x0910) 

>>>>>            << ItransMapItem("au", 0x0914) 

>>>>>            << ItransMapItem("a",  0x0905) 

>>>>>            << ItransMapItem("i",  0x0907) 

>>>>>            << ItransMapItem("u",  0x0909) 

>>>>>            << ItransMapItem("e",  QChar(0x0113), 0x090f) 

>>>>>            << ItransMapItem("o",  QChar(0x014d), 0x0913) 

>>>>>            << ItransMapItem("M",  QChar(0x1e43), 0x0902) 

>>>>>            << ItransMapItem("H",  QChar(0x1e25), 0x0903); 

>>>>>     map[1] << ItransMapItem("aa",  "A",  QChar(0x0101), 0x093e) 

>>>>>            << ItransMapItem("ii",  "I",   QChar(0x012b), 0x0940) 

>>>>>            << ItransMapItem("uu",  "U",   QChar(0x016b), 0x0942) 

>>>>>            << ItransMapItem("RRi", "R^i", QChar(0x1e5b), 0x0943) 

>>>>>            << ItransMapItem("RRI", "R^I", QChar(0x1e5d), 0x0944) 

>>>>>            << ItransMapItem("ai", 0x0948) 

>>>>>            << ItransMapItem("au", 0x094C) 

>>>>>            << ItransMapItem("i",  0x093f) 

>>>>>            << ItransMapItem("u",  0x0941) 

>>>>>            << ItransMapItem("e",  QChar(0x0113), 0x0947) 

>>>>>            << ItransMapItem("o",  QChar(0x014d), 0x094b); 

>>>>>     map[2] << ItransMapItem("kh", 0x0916) 

>>>>>            << ItransMapItem("gh", 0x0918) 

>>>>>            << ItransMapItem("~N", QChar(0x1e45), 0x0919) 

>>>>> //           << ItransMapItem("ch", 0x091a) 

>>>>> //           << ItransMapItem("Ch", 0x091b) 

>>>>>            << ItransMapItem("ch", 0x091b) 

>>>>>            << ItransMapItem("jh", 0x091d) 

>>>>>            << ItransMapItem("~n", QChar(0x00f1), 0x091e) 

>>>>>            << ItransMapItem("Th", QString("%1h").arg(QChar(0x1e6d)), 

>>>>> 0x0920) 

>>>>>            << ItransMapItem("Dh", QString("%1h").arg(QChar(0x1e0d)), 

>>>>> 0x0922) 

>>>>>            << ItransMapItem("th", 0x0925) 

>>>>>            << ItransMapItem("dh", 0x0927) 

>>>>>            << ItransMapItem("ph", 0x092b) 

>>>>>            << ItransMapItem("bh", 0x092d) 

>>>>>            << ItransMapItem("sh",  QChar(0x015b), 0x0936) 

>>>>>            << ItransMapItem("Sh",  QChar(0x1e63), 0x0937) 

>>>>>            << ItransMapItem("k",  0x0915) 

>>>>>            << ItransMapItem("g",  0x0917) 

>>>>>            << ItransMapItem("c",  0x091a) 

>>>>>            << ItransMapItem("j",  0x091c) 

>>>>>            << ItransMapItem("T",  QChar(0x1e6d), 0x091f) 

>>>>>            << ItransMapItem("D",  QChar(0x1e0d), 0x0921) 

>>>>>            << ItransMapItem("N",  QChar(0x1e47), 0x0923) 

>>>>>            << ItransMapItem("t",  0x0924) 

>>>>>            << ItransMapItem("d",  0x0926) 

>>>>>            << ItransMapItem("n",  0x0928) 

>>>>>            << ItransMapItem("p",  0x092a) 

>>>>>            << ItransMapItem("b",  0x092c) 

>>>>>            << ItransMapItem("m",  0x092e) 

>>>>>            << ItransMapItem("y",  0x092f) 

>>>>>            << ItransMapItem("r",  0x0930) 

>>>>>            << ItransMapItem("l",  0x0932) 

>>>>>            << ItransMapItem("v", "w", 0x0935) 

>>>>>            << ItransMapItem("w",  0x0935) 

>>>>>            << ItransMapItem("s",  0x0938) 

>>>>>            << ItransMapItem("h",  0x0939) 

>>>>>            << ItransMapItem("L",  0x0933); 

>>>>>     map[3] << ItransMapItem("0",  0x0966) 

>>>>>            << ItransMapItem("1",  0x0967) 

>>>>>            << ItransMapItem("2",  0x0968) 

>>>>>            << ItransMapItem("3",  0x0969) 

>>>>>            << ItransMapItem("4",  0x096a) 

>>>>>            << ItransMapItem("5",  0x096b) 

>>>>>            << ItransMapItem("6",  0x096c) 

>>>>>            << ItransMapItem("7",  0x096d) 

>>>>>            << ItransMapItem("8",  0x096e) 

>>>>>            << ItransMapItem("9",  0x096f); 

>>>>> } 

>>>>>  

>>>>> QString ItransDecoder::decode(QString txt) 

>>>>> { 

>>>>>     for (int i = 0; i < map[2].count(); i++) // consonant + virama 

>>>>>         txt.replace(QRegExp(map[2][i].txt), QString("%1%2").arg(QChar(

>>>>> map[2][i].code), QChar(0x094d))); 

>>>>>  

>>>>>     for (int i = 0; i < map[1].count(); i++) // consonant - virama + 

>>>>> vowels sign short 

>>>>>         txt.replace(QRegExp(QString("([\\x0915-\\x0939])\\x094d%1").

>>>>> arg(map[1][i].txt)), QString("\\1%1").arg(QChar(map[1][i].code))); 

>>>>>  

>>>>>     txt.replace(QRegExp("([\\x0915-\\x0939])\\x094da"), QString("\\1"

>>>>> )); // "a" 0x0000 

>>>>>  

>>>>>     for (int i = 0; i < map[0].count(); i++) 

>>>>>         txt.replace(QRegExp(map[0][i].txt), QChar(map[0][i].code)); 

>>>>>  

>>>>>     for (int i = 0; i < map[3].count(); i++) 

>>>>>         txt.replace(QRegExp(map[3][i].txt), QChar(map[3][i].code)); 

>>>>>  

>>>>>     return txt; 

>>>>> }

>>>>>

>>>>>

>>>>>

>>>>> The only modification of itrans.h is there-case replace of QString:

>>>>> struct ItransMapItem

>>>>> {

>>>>>     ItransMapItem(QString txt, int code)

>>>>>         : txt(REPLACE(txt)), code(code) {}

>>>>>     ItransMapItem(QString txt1, QString txt2, int code)

>>>>>         : txt(REPLACE(QString("(%1|%2)").arg(txt1, txt2))), code(code) 

>>>>> {}

>>>>>     ItransMapItem(QString txt1, QString txt2, QString txt3, int code)

>>>>>         : txt(REPLACE(QString("(%1|%2|%3)").arg(txt1, txt2, txt3))),code

>>>>> (code) {}

>>>>>

>>>>>     QString txt;

>>>>>     int     code;

>>>>> };

>>>>>

>>>>

## 10. Marcis — 2013-03-18 20:46:23

Шрифт-то интересно, как идут дела с ускорением загрузки?

On Monday, 18 March 2013 20:06:15 UTC+4, Artem Novikov wrote:
>
> Почему то считал, что шрифт не переопределить. 
> Хотя, если стиль меняется 
> myapp -stylesheet=stylesheet.qss
> то оказывается можно. Можете скрин заголовка окна карточки выложить (там 
> шрифт системный и программно не меняется)?
>
>

## 11. śrīdṛṣṭvā — 2013-03-19 12:14:15

Для сборки 1.1 ускорение загрузки может быть достигнуто уменьшением объема 
словарей...
Ну, а если создавать другие сборки, то для ускорения загрузки с точки 
зрения Артема есть вариант разпараллеливать на потоки, а с моей точки 
зрения надо <s>переписать всё</s> сделать суровую оптимизацию, путем 
полного изменения логики работы программы. Теоретически я могу это сделать, 
но на практике я не умею работать с типом данных "db" и чтобы избежать 
длительной загрузки программы (на нетбуке это 3 минуты), я просто не 
закрываю её (вот уже неделю), а вместо перезапуска делаю ноутбуку suspend.

> "Можете скрин заголовка окна карточки выложить"
Артем, в заголовке тоже шрифт меняется. Чтобы перекомпилить с новым шрифтом 
нужно:
१।make clean
२।rm Makefile
३।Меняем содержимое файлов config.h, sandic.qrc, css/app.css, css/doc.css
३-१।sandic.qrc:
<RCC>
     <qresource prefix="/">
         <file>Sanskrit_2003.ttf</file>
         <file>lang/qt_ru.qm</file>
         <file>lang/sandic_ru.qm</file>
         <file>css/app.css</file>
         <file>css/doc.css</file>
         <file>imgs/splash_en_EN.png</file>
         <file>imgs/splash_ru_RU.png</file>
     </qresource>
 </RCC>
३-२।В файлах अप्प्.च्स्स् च दोच्.च्स्स् च поменять Font Family на Sanskrit 
2003
३-३।В config.h прописать #define DAVAFONT "://Sanskrit_2003.ttf"
४।qmake
५।make
Кстати, со старым шрифтом बिनर्निकः весит १४७६३४५ बैतान्, а с этим шрифтом 
बिनर्निकः весит १०२१६९९ बैतान्।
что в полтора раза меньше ॥

Еще из полезного, я дописал в main.cpp такое:
QString dbfile=DBFILE;
if(argc==2)dbfile=argv[1];
if (!QFile::exists(dbfile)) {
...
}
...
db.setDatabaseName(dbfile);
db.open();
Что, собственно, позволяет выбирать db-файлик словари которого будут 
использованы, без перекомпиливания проэкта.


On Monday, March 18, 2013 10:46:23 AM UTC-7, Marcis wrote:
>
> Шрифт-то интересно, как идут дела с ускорением загрузки?
>
> On Monday, 18 March 2013 20:06:15 UTC+4, Artem Novikov wrote:
>>
>> Почему то считал, что шрифт не переопределить. 
>> Хотя, если стиль меняется 
>> myapp -stylesheet=stylesheet.qss
>> то оказывается можно. Можете скрин заголовка окна карточки выложить (там 
>> шрифт системный и программно не меняется)?
>>
>>

## 12. Artem Novikov — 2013-03-19 15:56:48

Я имел в виду, что программно из SnaDic шрифт заголовка окна не меняется, в 
мастдае он определяется настройками системы, возможно в бубунте это не так. 
Вариант с параметром как временное решение да еще на фоне дхату от 
Владислава более чем оправдано.

вторник, 19 марта 2013 г., 17:14:15 UTC+8 пользователь śrīdṛṣṭvā написал:
>
> Для сборки 1.1 ускорение загрузки может быть достигнуто уменьшением объема 
> словарей...
> Ну, а если создавать другие сборки, то для ускорения загрузки с точки 
> зрения Артема есть вариант разпараллеливать на потоки, а с моей точки 
> зрения надо <s>переписать всё</s> сделать суровую оптимизацию, путем 
> полного изменения логики работы программы. Теоретически я могу это сделать, 
> но на практике я не умею работать с типом данных "db" и чтобы избежать 
> длительной загрузки программы (на нетбуке это 3 минуты), я просто не 
> закрываю её (вот уже неделю), а вместо перезапуска делаю ноутбуку suspend.
>
> > "Можете скрин заголовка окна карточки выложить"
> Артем, в заголовке тоже шрифт меняется. Чтобы перекомпилить с новым 
> шрифтом нужно:
> १।make clean
> २।rm Makefile
> ३।Меняем содержимое файлов config.h, sandic.qrc, css/app.css, css/doc.css
> ३-१।sandic.qrc:
> <RCC>
>      <qresource prefix="/">
>          <file>Sanskrit_2003.ttf</file>
>          <file>lang/qt_ru.qm</file>
>          <file>lang/sandic_ru.qm</file>
>          <file>css/app.css</file>
>          <file>css/doc.css</file>
>          <file>imgs/splash_en_EN.png</file>
>          <file>imgs/splash_ru_RU.png</file>
>      </qresource>
>  </RCC>
> ३-२।В файлах अप्प्.च्स्स् च दोच्.च्स्स् च поменять Font Family на Sanskrit 
> 2003
> ३-३।В config.h прописать #define DAVAFONT "://Sanskrit_2003.ttf"
> ४।qmake
> ५।make
> Кстати, со старым шрифтом बिनर्निकः весит १४७६३४५ बैतान्, а с этим шрифтом 
> बिनर्निकः весит १०२१६९९ बैतान्।
> что в полтора раза меньше ॥
>
> Еще из полезного, я дописал в main.cpp такое:
> QString dbfile=DBFILE;
> if(argc==2)dbfile=argv[1];
> if (!QFile::exists(dbfile)) {
> ...
> }
> ...
> db.setDatabaseName(dbfile);
> db.open();
> Что, собственно, позволяет выбирать db-файлик словари которого будут 
> использованы, без перекомпиливания проэкта.
>
>
> On Monday, March 18, 2013 10:46:23 AM UTC-7, Marcis wrote:
>>
>> Шрифт-то интересно, как идут дела с ускорением загрузки?
>>
>> On Monday, 18 March 2013 20:06:15 UTC+4, Artem Novikov wrote:
>>>
>>> Почему то считал, что шрифт не переопределить. 
>>> Хотя, если стиль меняется 
>>> myapp -stylesheet=stylesheet.qss
>>> то оказывается можно. Можете скрин заголовка окна карточки выложить (там 
>>> шрифт системный и программно не меняется)?
>>>
>>>

## 13. Artem Novikov — 2013-03-19 15:58:49

Никак, на данный момент я этим не занимаюсь. Вначале я хочу изменить 
структуру БД, затем уже можно пытаться заняться оптимизацией.

вторник, 19 марта 2013 г., 1:46:23 UTC+8 пользователь Marcis написал:
>
> Шрифт-то интересно, как идут дела с ускорением загрузки?
>
> On Monday, 18 March 2013 20:06:15 UTC+4, Artem Novikov wrote:
>>
>> Почему то считал, что шрифт не переопределить. 
>> Хотя, если стиль меняется 
>> myapp -stylesheet=stylesheet.qss
>> то оказывается можно. Можете скрин заголовка окна карточки выложить (там 
>> шрифт системный и программно не меняется)?
>>
>>

## 14. śrīdṛṣṭvā — 2013-03-19 17:50:00

Понял, пересмотрел старую версию, увидел в заголовках вовсе не siddhanta. 
Высказывание "в заголовке тоже шрифт меняется" оказалось ложно — шрифт 
заголовка определяется настройками системы.

On Tuesday, March 19, 2013 5:56:48 AM UTC-7, Artem Novikov wrote:
>
> Я имел в виду, что программно из SnaDic шрифт заголовка окна не меняется, 
> в мастдае он определяется настройками системы, возможно в бубунте это не 
> так. Вариант с параметром как временное решение да еще на фоне дхату от 
> Владислава более чем оправдано.
>
> вторник, 19 марта 2013 г., 17:14:15 UTC+8 пользователь śrīdṛṣṭvā написал:
>>
>> Для сборки 1.1 ускорение загрузки может быть достигнуто уменьшением 
>> объема словарей...
>> Ну, а если создавать другие сборки, то для ускорения загрузки с точки 
>> зрения Артема есть вариант разпараллеливать на потоки, а с моей точки 
>> зрения надо <s>переписать всё</s> сделать суровую оптимизацию, путем 
>> полного изменения логики работы программы. Теоретически я могу это сделать, 
>> но на практике я не умею работать с типом данных "db" и чтобы избежать 
>> длительной загрузки программы (на нетбуке это 3 минуты), я просто не 
>> закрываю её (вот уже неделю), а вместо перезапуска делаю ноутбуку suspend.
>>
>> > "Можете скрин заголовка окна карточки выложить"
>> Артем, в заголовке тоже шрифт меняется. Чтобы перекомпилить с новым 
>> шрифтом нужно:
>> १।make clean
>> २।rm Makefile
>> ३।Меняем содержимое файлов config.h, sandic.qrc, css/app.css, css/doc.css
>> ३-१।sandic.qrc:
>> <RCC>
>>      <qresource prefix="/">
>>          <file>Sanskrit_2003.ttf</file>
>>          <file>lang/qt_ru.qm</file>
>>          <file>lang/sandic_ru.qm</file>
>>          <file>css/app.css</file>
>>          <file>css/doc.css</file>
>>          <file>imgs/splash_en_EN.png</file>
>>          <file>imgs/splash_ru_RU.png</file>
>>      </qresource>
>>  </RCC>
>> ३-२।В файлах अप्प्.च्स्स् च दोच्.च्स्स् च поменять Font Family на 
>> Sanskrit 2003
>> ३-३।В config.h прописать #define DAVAFONT "://Sanskrit_2003.ttf"
>> ४।qmake
>> ५।make
>> Кстати, со старым шрифтом बिनर्निकः весит १४७६३४५ बैतान्, а с этим 
>> шрифтом बिनर्निकः весит १०२१६९९ बैतान्।
>> что в полтора раза меньше ॥
>>
>> Еще из полезного, я дописал в main.cpp такое:
>> QString dbfile=DBFILE;
>> if(argc==2)dbfile=argv[1];
>> if (!QFile::exists(dbfile)) {
>> ...
>> }
>> ...
>> db.setDatabaseName(dbfile);
>> db.open();
>> Что, собственно, позволяет выбирать db-файлик словари которого будут 
>> использованы, без перекомпиливания проэкта.
>>
>>
>> On Monday, March 18, 2013 10:46:23 AM UTC-7, Marcis wrote:
>>>
>>> Шрифт-то интересно, как идут дела с ускорением загрузки?
>>>
>>> On Monday, 18 March 2013 20:06:15 UTC+4, Artem Novikov wrote:
>>>>
>>>> Почему то считал, что шрифт не переопределить. 
>>>> Хотя, если стиль меняется 
>>>> myapp -stylesheet=stylesheet.qss
>>>> то оказывается можно. Можете скрин заголовка окна карточки выложить 
>>>> (там шрифт системный и программно не меняется)?
>>>>
>>>>

_Dr. Mārcis Gasūns_

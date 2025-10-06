# KSP-console-to-PC-save-converter

work in progress, should be done in the next few days (start of october)
if you're reading this, its not yet ready for use!





# Requirements and instructions
## Requirements:


## Important notes:

A demo video: 

1. I use ‘savegame’ to refer to the options seen on the ‘load game’ menu on the main menu. I use ‘quicksaves’ to refer to the options seen in the ‘load’ menu on the pause menu while in a savegame.

2. As far as I know, no major data is lost when converting, but I haven’t had much time to test it. Will update this page when I get the chance to check it all.

3. I’ve written this page for use with a Windows computer and an Xbox. 
This should still work on Mac and Linux, albeit some instructions might be wrong (e.g. there is no Microsoft Store on Mac or Linux). Use equivalent methods for them.\
***As for Playstation*** – The Playstation edition is very similar to the Xbox edition, if not identical, and their save structures are the same. Therefore, the .py extractor on this page can be used on their files too. However, you'll need another way to actually get the save files off the console; this page only has instructions for downloading the saves off of Xboxes (steps 1-3). I've heard that the PS4 can download savefiles onto USB, and apparently there is a subscription service for Playstation 5 that allows uploading savefiles to the cloud. -- edit: I have confirmed that you can indeed download save files from ps4 and ps5, but they are encrypted and in an unreadable format. I have no experience in ps4 or ps5 tools, but it seems like they can be decrypted using other tools. You'll need to do that before using the standalone .py programs here.  
Therefore, steps 1 to 3 are for Xbox only (as they are instructions to download the saves from an Xbox) but I still *highly recommend* reading step 3, as it includes info that is seen in the Playstation version too. Steps 4 and 5 apply to both consoles - once you have obtained the save files from a playstation, you may proceed to step 3/4. Do also note that I may mention Xbox buttons or Xbox saves, but generally you can replace it with an equivalent process or word for Playstation.

5. 


## Instructions:



1. Your KSP saves should be backed up to the Xbox Network. That is, ensure you’ve been online while running the game, perhaps leave it running for a little while with a savegame loaded to make sure it has backed up the latest saves.

2. **Running the downloader:** You should have Git and UV installed by this point. You should also download the whole repo, as we'll be using all of the files contained here - by clicking the green 'code' button and downloading as a ZIP. extract it to a location of your choice; preferably somewhere not too deep in directories, because Windows has a 256 character limit when inputting paths for some of the python programs, and it can cause problems. Open powershell and type in, then enter, `cd [path of Downloader (modified spark downloader)]` - without the square brackets, and the path will need quotation marks on the start and end if the way you copied it in didn't automatically insert them. Next, type and enter `uv run xbox-savegame-cli`. That should trigger the program to run; once its ready, it should prompt you with a link to copy and paste into a browser. The way this downloader works, it acts as a standard linked application that requests, through the official Microsoft login portal, to read basic profile data. It will prompt you to login if you aren't already[^1] and then that sends the token off onto another URL; which doesn't actually work. This is what needs to be pasted back into the program, because it is able to use that broken link to read savedata associated with your profile. It should then accept the link, and eventually tell you that "savefiles have been downloaded to ...". Note that it will download a regular folder copy of them, and a ZIP copy of them - this ZIP copy can be extracted and used as a backup if something goes wrong.

3. **Converting the savefiles to the PC version:** You should have Python installed by this point. At the moment, your savefiles can be found within "Downloader (modified spark downloader"/downloads/cli_user_[number]/SaveData/" - however, they are currently in a raw, compressed-folder format and not readable. "extractor.py" will extract and convert them to a PC-readable format: to run it, type and enter into powershell or command prompt: `python [path of extractor.py] [path of the input folder] [path of the output folder]` again, wihout square brackets, and with quotation marks if not automatically inserted, and - you will need to make a new folder (output folder) somewhere on your device, into which the extractor will convert the files. The end result of this should be a bunch of folders with gibberish names - these are the standard PC KSP savegame folders that are usually found in "[drive]:\Program Files (x86)\Steam\steamapps\common\Kerbal Space Program\saves\"

5. **Final repairing:** The remaining .py programs can be run in any order, but I generally recommend running the savegame-folder-renamer first. Unlike the extractor, these programs don't need output folders; they run in-place, replacing what is already there. for these, the command is `python [path of the .py program] [path of the input folder]` with the input folder being the folder that contains the savegame folders. After all 4 applications have been run, you are done - you may put all the savegame folders into the usual directory outlined in the above step.

Enjoy!

[^1]: (logging into a microsoft service previously during that browser session should mean it automatically redirects you to the following URL) - This means that, if you are understandably uncomfortable with entering your login details on some random link provided to you, you can login to your account on the official microsoft website, then open the link - as it uses the official Microsoft web authentication API, it can use the browser session token and you won't be prompted to log in.

Should you wish to now deny the application's access to read your profile data, you can do so in Microsoft Account settings online.

# Credits

- Massive thanks to [tuxuser](https://www.github.com/tuxuser) - he did all of the programming, reverse engineering, everything to do with manipulating the savefiles to make them readable. He did the decompression, the blob extraction (unpacking), the compiling, the decompiling, the algorithm analysis, the encryption-related-documentation reading, the assembly.. a lot. Thanks, man!! Edit: He also coincidentally did a lot of work on the Project Spark Downloader (and, by extension, this project's downloader), and the webAPI auth service relies on.
- Me - I wrote the documentation, and put a few puzzle pieces together regarding how to take the savefiles off an Xbox and how to interpret them.
- [Billynothingelse](https://www.github.com/billynothingelse) - for having created the save transferer program that would end up being my holy grail, after I struggled to find any method that worked.
- JonnyOThan, over on discord - helped with some questions I had about the savefiles.
- Falcon, on discord - for doing nearly all the work on fixing the part name mismatch bug, and verifying that the modified save downloader worked.
-Soltinator, for creating the [Project Spark Downloader](https://github.com/ProjectSparkDev/SparkXboxSavegameDownloader)
- Everyone who said this was impossible - You awakened the stubbornness in me, and made me pursue this further.
- Everyone else who uses this - I hope this helps you, and you do something fun/cool with it.



# Faq/common errors, and bugs

## Python:

- **“Errno 2: no such file or directory”:** Ensure you include the ‘.py’ extension in the filename for the program path.

- **multiple exceptions with the last one being about a ZIP creation** - path to the output folder is too long and exceeds windows' limit. please put it somewhere else temporarily, like on your desktop.

## Bugs:
- The 'common' pseudo-folder-file (which includes scenario saves and tutorial saves) doesn't work straight up - I've been extremely busy and haven't had much time at all to test anything.

- ~~Need to test and fix DLC part names' mismatches~~ -**fixed, see the [more info](#-More-info/backstory) section.**

# Examples (see hashtags above)

#1. If I had the python extractor with the path ‘C:\Users\JohnDoe\Desktop\python extractor\extract.py’, and had the input pseudo-folder-file from xbcsmgr with the path ‘C:\Users\JohnDoe\Desktop\xbcsmgrfiles\gibberishname’, and wanted to output it to a folder with the path ‘C:\Users\JohnDoe\Desktop\outputkspsavegames\gibberishname1\’, I would use the command ‘python “C:\Users\JohnDoe\Desktop\python extractor\extract.py” C:\Users\JohnDoe\Desktop\xbcsmgrfiles\gibberishname C:\Users\JohnDoe\Desktop\outputkspsavegames\gibberishname1\’ (the first path has quotation marks as it contains a space, otherwise cmd would treat the path as 2 separate terms).




# More info/backstory
I started playing KSP on the Xbox, and since I first started I immediately knew I’d rather play on PC. Especially as I have an Xbox One S, arguably underpowered even for a 10 year old game like KSP. ‘Optimised and enhanced for Xbox’ my ass!
In about October 2024, I started launching bigger ships and realised I really need to find a way to transfer my savefile to PC, because my Xbox wasn’t tolerating it at all.
I asked about whether it would be possible to transfer the savefile across on the KSP reddit’s discord. Everyone said it was impossible. 
Anyway… I’m too stubborn for anyone’s good, so I joined multiple Xbox modding scene servers, trying to gather information on how savefiles work (in terms of Xbox’s functions), how I could transfer it, and how the savefiles might work on KSP’s side.
Eventually, I met [tuxuser](https://www.github.com/tuxuser). I was entirely planning on figuring out transferring, encryption, and programming of the transfer application myself, but in the end Tuxuser did almost all of it (thanks again, man!)
Here’s what we looked at, in order:
Getting the files from the Xbox in the first place. I tried numerous methods, including taking the HDD out and connecting it via PC to decrypt it using various Github projects ( – which didn’t work: I first had a look at the partitions windows had discovered without any conversion program – of which there was only one that was readable by windows; I tried a conversion program by Github user ‘gitfurious’ and managed to get the python program running, but it would always fail and spit out an error… likely due to a lack of skills on my part; and tried one by user ‘brandonreynolds’ which I remember did error a few times when trying to launch it in visual studio… I don’t remember whether I got it working in the end – I think it did succeed in converting partitions into a windows-readable format, but the partitions/drives that were shown in file explorer afterwards were all of the same ones shown in ADV file explorer on Xbox – i.e. all of the partitions that are hidden in ADV were also missing here. I’m not sure whether this is due to a fault in the conversion, or that the partitions were still hidden somehow… perhaps those partitions are encrypted and either the converter or windows couldn’t read it. Anyhow, I then switched methods and tried a cloud save manager (xbcsmgr) which found the savefiles…

 … albeit it downloaded any and all files in raw form, with no file extensions. The savefiles could be opened via text/hex editors only, and it was mostly garbled Unicode with a bit of plaintext mixed in. I then confirmed that the files were fully intact and readable – I downloaded (via xbcsmgr) a Minecraft: Xbox One Edition savefile, which had a file in it that, when opened in a text editor (notepad :) ), showed some plaintext, including the letters ‘.jpg’. I added .jpg onto the end of file name and voila, it worked, a functioning image. I presume this plaintext, which is also present in the KSP files, must be a file header or metadata or something along those lines.
 
I took a look at the KSP savefiles again. We determined that the files that xbcsmgr downloaded[a] (in my case, there were 2 files with gibberish 26 letter words as filenames, which I later determined were the 2 savegames I had; and 1 file with the name ‘common’, which I later determined to contain the scenario savegames, and possibly other things) were actually folders containing files in them, as these pseudo-folder files[a] (which mostly contained gibberish Unicode) contained multiple small sections of plaintext that appeared to be strings of filenames and extensions, which we presumed were the headers for the files in these pseudo-folder files. It made more sense this way, anyway, as that’s how the savegames files are stored on PC – in folders, also laid out in that way.

Tux (and separately, a discord user, JonnyOThan, but I forgot to tell Tux so he eventually figured it out on his own :sweat_smile: ) noticed that there were repeating patterns in the pseudo-folder-files, that there were many headers and accompanying data. He determined that these were the actual files and folder structures we want, and called each of them blobs. He wrote a python program to extract the blobs out of the pseudo-folder-files. This yielded a lot of smaller files and folders, with correct filenames, and seemingly correct file extensions… except that they were compressed, with a ‘.cmp’ file extension after the correct one in the filename. We had extracted all the files from the pseudo-folder-files into their correct layout as per the PC version of the game, but they were compressed.

Tux set out to figure out what compression was being used. He took a quick look at the blobs, and considered LZMA compression after realising that the file headers have specific features that are seen in headers formed by LZMA compression. He then checked out a PS4 dump of the game, which had a file named ‘tempsavemanager.prx’; that lead him to consider and try to match up the blobs with XML identifier lookup table compression, but then found a function named ‘LzmaDecompress’ in the .prx file so went back to trying LZMA. He tried recreating the decompression algorithm to no avail, and tried various unpackers, also to no avail. Finally, he discovered that LZMA can have an extra parameter called ‘FORMAT_RAW’, and manually assembled the LZMA ‘filter chain’ through trial and error; and putting this all together into a homemade decompressor finally returned plaintext data for all the files.


A few months later, the old xbcsmgr method of downloading savefiles from the Xbox Network, no longer works - an update to the Windows Xbox App, which it relied on, altered how authentication worked. In response (and because I was working with Falcon to fix some bugs), I set out to find another method to download the savefiles, and started by looking at forks of xbcsmgr - which led me to [the Project Spark Downloader](https://github.com/ProjectSparkDev/SparkXboxSavegameDownloader). That downloader is a modified version of xbcsmgr, patched to work by using a different authentication method, a web-based one. It was also converted to python, from c#. However, the Project Spark Downloader had been set to work only on Project Spark saves. This project is a modified version of that, to allow for KSP saves to download instead, and with the KSP save converter and the parts renamer included.
Changes between the Project Spark Downloader and this project:
- games.json edited to work with KSP saves
- .env edited to work straight away from download, versus having the user input values
- removed discord bot functionality - this project currently only uses the CLI program form of the Project Spark Downloader. - discord bot functionality could be added back in relatively easily.
- removed a couple steps of the CLI program when it did not make sense for KSP saves (e.g. files cleanup step, games choice/select step)
- note to self: Discord bot outputs games' title ID in hexadecimal! Do not try to put the title ID value straight into the games.json without converting to decimal first!

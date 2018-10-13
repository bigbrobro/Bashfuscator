"""
String Obfuscators used by the framework.
"""
import math
import hashlib
import string

from bashfuscator.common.helpers import escapeQuotes
from bashfuscator.common.objects import Mutator


class StringObfuscator(Mutator):
    """
    Base class for all String Obfuscators. A String Obfuscator is a
    Mutator that builds the input string by executing a series of
    commands to build chunks of the original string, and reorganizing
    and concatenating those chunks to reassemble the original string.

    :param name: name of the StringObfuscator
    :type name: str
    :param description: short description of what the StringObfuscator 
            does
    :type description: str
    :param sizeRating: rating from 1 to 5 of how much the 
            StringObfuscator increases the size of the overall payload
    :type sizeRating: int
    :param timeRating: rating from 1 to 5 of how much the
            StringObfuscator increases the execution time of the overall
            payload
    :type timeRating: int
    :param binariesUsed: list of all the binaries the StringObfuscator
            uses
    :type binariesUsed: list of strs
    :param fileWrite: True if the Command Obfuscator requires 
            creating/writing to files, False otherwise
    :type fileWrite: bool
    :param notes: see :class:`bashfuscator.common.objects.Mutator`
    :type notes: str
    :param author: see :class:`bashfuscator.common.objects.Mutator`
    :type author: str
    :param credits: see :class:`bashfuscator.common.objects.Mutator`
    :type credits: str
    """

    def __init__(self, name, description, sizeRating, timeRating, binariesUsed=[], fileWrite=False, notes=None, author=None, credits=None):
        super().__init__(name, "string", notes, author, credits)

        self.description = description
        self.sizeRating = sizeRating
        self.timeRating = timeRating
        self.fileWrite = fileWrite
        self.binariesUsed = binariesUsed
        self.originalCmd = ""
        self.payload = ""


class GlobObfuscator(StringObfuscator):
    def __init__(self, name, description, sizeRating, timeRating, author):
        super().__init__(
            name=name,
            description=description,
            sizeRating=sizeRating,
            timeRating=timeRating,
            binariesUsed=["cat", "mkdir", "rm"],
            fileWrite=True,
            author=author
        )

        self.writeableDir = ""
        self.workingDir = ""
        self.minDirLen = None
        self.maxDirLen = None
        self.sectionSize = None

    def generate(self, sizePref, userCmd, writeDir=None):
        self.writeableDir = (writeDir + self.randGen.randUniqueStr(self.minDirLen, self.maxDirLen))

        self.workingDir = escapeQuotes(self.writeableDir)

        cmdChars = [userCmd[i:i + self.sectionSize] for i in range(0, len(userCmd), self.sectionSize)]
        cmdLen = len(cmdChars)
        cmdLogLen = int(math.ceil(math.log(cmdLen, 2)))
        if cmdLogLen <= 0:
            cmdLogLen = 1

        parts = []
        for i in range(cmdLen):
            ch = cmdChars[i]
            ch = escapeQuotes(ch)
            parts.append(
                "printf %s '" + ch + "' > '" + self.workingDir + "/" +
                format(i, "0" + str(cmdLogLen) + "b").replace("0", "?").replace("1", "\n") + "';"
            )
        self.randGen.randShuffle(parts)

        # TODO: randomize ordering of 'rm' statements
        self.payload = ""
        self.payload += "mkdir -p '" + self.workingDir + "';"
        self.payload += "".join(parts)
        self.payload += "cat '" + self.workingDir + "'/" + "?" * cmdLogLen + ";"
        self.payload += "rm '" + self.workingDir + "'/" + "?" * cmdLogLen + ";"

    def setSizes(self, sizePref, userCmd):
        if sizePref == 0:
            self.minDirLen = self.maxDirLen = 1
            self.sectionSize = int(len(userCmd) / 3 + 1)
        elif sizePref == 1:
            self.minDirLen = 1
            self.maxDirLen = 3
            self.sectionSize = int(len(userCmd) / 10 + 1)
        elif sizePref == 2:
            self.minDirLen = 6
            self.maxDirLen = 12
            self.sectionSize = int(len(userCmd) / 100 + 1)
        elif sizePref == 3:
            self.minDirLen = 12
            self.maxDirLen = 24
            self.sectionSize = 3
        elif sizePref == 4:
            self.minDirLen = self.maxDirLen = 32
            self.sectionSize = 1


class FileGlob(GlobObfuscator):
    def __init__(self):
        super().__init__(
            name="File Glob",
            description="Uses files and glob sorting to reassemble a string",
            sizeRating=5,
            timeRating=5,
            author="elijah-barker"
        )

    def mutate(self, sizePref, timePref, userCmd):
        self.originalCmd = userCmd

        self.setSizes(sizePref, userCmd)
        self.generate(sizePref, userCmd, self.writeDir)

        return self.payload


class FolderGlob(GlobObfuscator):
    def __init__(self):
        super().__init__(
            name="Folder Glob",
            description="Same as file glob, but better",
            sizeRating=5,
            timeRating=5,
            author="elijah-barker"
        )

    def mutate(self, sizePref, timePref, userCmd):
        self.originalCmd = userCmd

        self.setSizes(sizePref, userCmd)
        self.writeableDir = (self.writeDir + self.randGen.randUniqueStr(self.minDirLen, self.maxDirLen))
        self.workingDir = escapeQuotes(self.writeableDir)

        cmdChunks = [userCmd[i:i + self.sectionSize] for i in range(0, len(userCmd), self.sectionSize)]
        parts = []

        # TODO: remove created folders
        for chunk in cmdChunks:
            self.generate(sizePref, chunk, self.writeableDir + "/" + self.randGen.randUniqueStr(self.minDirLen, self.maxDirLen))
            parts.append(self.payload)

        self.payload = "".join(parts)

        return self.payload


class ForCode(StringObfuscator):
    def __init__(self):
        super().__init__(
            name="ForCode",
            description="Shuffle command and reassemble it in a for loop",
            sizeRating=2,
            timeRating=3,
            author="capnspacehook",
            credits="danielbohannon, https://github.com/danielbohannon/Invoke-DOSfuscation"
        )

    def mutate(self, sizePref, timePref, userCmd):
        self.originalCmd = userCmd

        # get a set of unique chars in original command
        shuffledCmd = list(set(userCmd))
        self.randGen.randShuffle(shuffledCmd)
        shuffledCmd = "".join(shuffledCmd)

        # build a list of the indexes of where each char in the original command
        # is in the array that holds the individual chars
        ogCmdIdxes = []
        for char in userCmd:
            ogCmdIdxes.append(shuffledCmd.find(char))

        cmdIndexes = "".join([str(i) + " " for i in ogCmdIdxes])[:-1]

        # escape special chars
        specialChars = string.punctuation + " "
        tempStr = shuffledCmd
        shuffledCmd = ""
        for char in tempStr:
            if char in specialChars:
                char = "\\" + char

            shuffledCmd += char + " "

        shuffledCmd = shuffledCmd[:-1]

        charArrayVar = self.randGen.randGenVar(sizePref)
        obCmd = "{0}=({1});".format(charArrayVar, shuffledCmd)

        indexVar = self.randGen.randGenVar(sizePref)
        obCmd += "for {0} in {1}".format(indexVar, cmdIndexes)

        if self.randGen.probibility(50):
            obCmd += ';{{ printf %s "${{{0}[${1}]}}"; }}'.format(charArrayVar, indexVar)
        
        else:
            obCmd += ';do printf %s "${{{0}[${1}]}}";done'.format(charArrayVar, indexVar)

        self.payload = obCmd

        return self.payload


class HexHash(StringObfuscator):
    def __init__(self):
        super().__init__(
            name="Hex Hash",
            description="Uses the output of md5 to encode strings",
            sizeRating=5,
            timeRating=5,
            binariesUsed=["cut", "md5sum"],
            author="elijah-barker"
        )

    def mutate(self, sizePref, timePref, userCmd):
        self.originalCmd = userCmd

        obCmd = ""
        for ch in userCmd:
            hexchar = str(bytes(ch, "utf-8").hex())
            randomhash = ""

            while not hexchar in randomhash:
                m = hashlib.md5()
                randomString = self.randGen.randGenStr(1, 3)
                m.update(bytes(randomString, "utf-8"))
                randomhash = m.digest().hex()

            index = randomhash.find(hexchar)
            obCmd += 'printf "\\x$(printf \'' + randomString + "\'|md5sum|cut -b" + str(index + 1) + "-" + str(index + 2) + ')";'

        self.payload = obCmd

        return self.payload

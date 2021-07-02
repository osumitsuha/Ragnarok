import aiofiles

class HitObject:
    def __init__(self):
        self.time: int = 0

        self.x: int = 0
        self.y: int = 0
        self.xy: int = 0

    @classmethod
    def from_str(cls, line, hr: bool = False):
        args = line.split(",")   
        
        s = cls()

        s.time = int(args[2])
        s.x = int(args[0])
        s.y = 384 - int(args[1]) if hr else int(args[1])

        s.xy = s.x + s.y

        return s


class Beatmap(list):
    async def parse_hitobjects(self, file_name: str, hr: bool = False): 
        lines = None

        async with aiofiles.open(file_name, "r") as file: 
            lines = await file.readlines()

        for idx, line in enumerate(lines):
            if line == "[HitObjects]\n":
                lines = lines[idx+1:]

        for line in lines:
            super().append(HitObject.from_str(line))

        return self


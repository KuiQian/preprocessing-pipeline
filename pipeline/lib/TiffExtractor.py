import os, glob
import hashlib
from lib.ParallelManager import ParallelManager
from lib.CZIManager import extract_tiff_from_czi, extract_png_from_czi


class TiffExtractor(ParallelManager):
    def extract_tifs_from_czi(self):
        """
        This method will:
            1. Fetch the meta information of each slide and czi files from the database
            2. Extract the images from the czi file and store them as tiff format with the bioformats tool.
            3. Then updates the database with meta information about the sections in each slide
        Args:
            animal: the prep id of the animal
            channel: the channel of the stack image to process
            compression: Compression used to store the tiff files default is LZW compression

        Returns:
            nothing
        """
        if not self.downsample:
            OUTPUT = self.fileLocationManager.tif
            scale_factor = 1
        else:
            OUTPUT = self.fileLocationManager.thumbnail_original
            scale_factor = 0.03125
        INPUT = self.fileLocationManager.czi
        os.makedirs(OUTPUT, exist_ok=True)
        starting_files = glob.glob(
            os.path.join(OUTPUT, "*_C" + str(self.channel) + ".tif")
        )
        total_files = os.listdir(OUTPUT)
        self.logevent(f"TIFF EXTRACTION FOR CHANNEL: {self.channel}")
        self.logevent(f"OUTPUT FOLDER: {OUTPUT}")
        self.logevent(f"FILE COUNT [FOR CHANNEL {self.channel}]: {len(starting_files)}")
        self.logevent(f"TOTAL FILE COUNT [FOR DIRECTORY]: {len(total_files)}")

        sections = self.sqlController.get_distinct_section_filenames(
            self.animal, self.channel
        )

        czi_file = []
        tif_file = []
        scene_index = []
        for section in sections:
            input_path = os.path.join(INPUT, section.czi_file)
            outfile = os.path.basename(section.file_name)
            output_path = os.path.join(OUTPUT, outfile)
            if not os.path.exists(input_path):
                continue
            if os.path.exists(output_path):
                continue
            czi_file.append(input_path)
            tif_file.append(output_path)
            scene_index.append(section.scene_number - 1)
        workers = self.get_nworkers()
        nfiles = len(czi_file)
        channel = [self.channel for _ in range(nfiles)]
        scale = [scale_factor for _ in range(nfiles)]

        self.run_commands_in_parallel_with_executor(
            [czi_file, tif_file, scene_index, channel, scale],
            workers,
            extract_tiff_from_czi,
        )
        self.update_database()

    def update_database(self):
        """Updating the file log table in the database about the completion of the QC preparation steps"""
        self.sqlController.set_task(
            self.animal, self.progress_lookup.QC_IS_DONE_ON_SLIDES_IN_WEB_ADMIN
        )
        self.sqlController.set_task(
            self.animal,
            self.progress_lookup.CZI_FILES_ARE_CONVERTED_INTO_NUMBERED_TIFS_FOR_CHANNEL_1,
        )

    def calc_filechecksum(self, filename, channel):
        sha256_hash = hashlib.sha256()

        if filename.find("_") != -1:
            path_to_full_resolution_tiff = os.path.join(
                self.fileLocationManager.tif, filename
            )
        else:
            path_to_full_resolution_tiff = os.path.join(
                self.fileLocationManager.prep, "CH" + str(channel), filename
            )
        with open(path_to_full_resolution_tiff, "rb") as f:
            # Read and update hash string value in blocks of 4K
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
            checksum = str(sha256_hash.hexdigest())
        print(
            sha256_hash.hexdigest(),
            "\t",
            os.path.basename(path_to_full_resolution_tiff),
            "\n",
        )
        return checksum

    def create_web_friendly_image(self):
        """Create downsampled version of full size tiff images that can be viewed on the Django admin portal
        These images are used for Quality Control
        ONLY 1 CHANNEL CREATED FOR .png FILES
        """
        INPUT = self.fileLocationManager.czi
        OUTPUT = self.fileLocationManager.thumbnail_web
        channel = 1
        os.makedirs(OUTPUT, exist_ok=True)
        czi_file = []
        files = os.listdir(INPUT)

        sections = self.sqlController.get_distinct_section_filenames(
            self.animal, channel
        )
        self.logevent(f"SINGLE (FIRST) CHANNEL ONLY - SECTIONS: {len(sections)}")
        self.logevent(f"OUTPUT FOLDER: {OUTPUT}")

        file_keys = []
        files_skipped = 0
        for i, section in enumerate(sections):
            infile = os.path.join(INPUT, section.czi_file)
            outfile = os.path.basename(section.file_name)
            output_path = os.path.join(OUTPUT, outfile)
            outfile = output_path[:-5] + "1.png"  # force "C1" in filename
            if os.path.exists(outfile):
                files_skipped += 1
                print(f"SKIP: {outfile}")
                continue
            scene_index = section.scene_number - 1
            scale = 0.01
            file_keys.append([i, infile, outfile, scene_index, scale])

        self.logevent(f"SKIPPED [PRE-EXISTING] FILES: {files_skipped}")
        n_processing_elements = len(file_keys)
        self.logevent(f"PROCESSING [NOT PRE-EXISTING] FILES: {n_processing_elements}")

        workers = self.get_nworkers()
        batch_size = workers  # mem not issue due to filesize
        self.run_commands_in_parallel_with_executor(
            [file_keys], workers, extract_png_from_czi, batch_size=batch_size
        )

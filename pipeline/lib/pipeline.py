"""
This class is used to run the entire preprocessing pipeline - 
from CZI files to a pyramid of tiles that can be viewed in neuroglancer.

Args are animal, channel, and downsample. With animal being
the only required argument.
All imports are listed by the order in which they are used in the 
"""

import os
import sys
from shutil import which
import shutil
import threading
from xml.dom.pulldom import START_DOCUMENT
from lib.FileLocationManager import FileLocationManager
from lib.MetaUtilities import MetaUtilities
from lib.PrepCreater import PrepCreater
from lib.NgPrecomputedMaker import NgPrecomputedMaker
from lib.NgDownsampler import NgDownsampler
from lib.ProgressLookup import ProgressLookup
from lib.TiffExtractor import TiffExtractor
from timeit import default_timer as timer
from Controllers.SqlController import SqlController
from lib.FileLogger import FileLogger
from lib.logger import get_logger
from lib.ParallelManager import ParallelManager
from lib.Normalizer import Normalizer
from lib.MaskManager import MaskManager
from lib.ImageCleaner import ImageCleaner
from lib.HistogramMaker import HistogramMaker
from lib.ElastixManager import ElastixManager


class Pipeline(
    MetaUtilities,
    TiffExtractor,
    PrepCreater,
    ParallelManager,
    Normalizer,
    MaskManager,
    ImageCleaner,
    HistogramMaker,
    ElastixManager,
    NgPrecomputedMaker,
    NgDownsampler,
    FileLogger,
):
    """
    This is the main class that handles the preprocessing pipeline responsible for converting Zeiss microscopy images (.czi) into neuroglancer
    viewable formats.  The Zeiss module can be swapped out to make the pipeline compatible with other microscopy setups
    """

    def __init__(
        self,
        animal,
        channel=1,
        downsample=True,
        DATA_PATH="/net/birdstore/Active_Atlas_Data/data_root",
        host="db.dk.ucsd.edu",
        schema="active_atlas_production",
        debug=False,
        padding_margin=1,
    ):
        """Setting up the pipeline and the processing configurations
        Here is how the Class is instantiated:
            pipeline = Pipeline(animal, channel, downsample, data_path, host, schema, debug)

           The pipeline performst the following steps:
           1. extracting the images from the microscopy formats (eg czi) to tiff format
           2. Prepare thumbnails of images for quality control
           3. clean the images
           4. align the images
           5. convert to Seung lab neuroglancer cloudvolume format

           step 3 and 4 are first performed on downsampled images, and the image masks(for step 3) and the within stack alignments(for step 4) are
           upsampled for use in the full resolution images

        Args:
            animal (str): Animal Id
            channel (int, optional): channel number.  This tells the program which channel to work on and which channel to extract from the czis. Defaults to 1.
            downsample (bool, optional): Determine if we are working on the full resolution or downsampled version. Defaults to True.
            DATA_PATH (str, optional): path to where the images and intermediate steps are stored. Defaults to '/net/birdstore/Active_Atlas_Data/data_root'.
            debug (bool, optional): determine if we are in debug mode.  This is used for development purposes. Defaults to False. (forces processing on single core)
        """
        self.animal = animal
        self.channel = channel
        self.ch_dir = f"CH{self.channel}"
        self.downsample = downsample
        self.debug = debug
        self.fileLocationManager = FileLocationManager(animal, DATA_PATH=DATA_PATH)
        self.sqlController = SqlController(animal, host, schema)
        self.hostname = self.get_hostname()
        self.dbhost = host
        self.dbschema = schema
        self.load_parallel_settings()
        self.progress_lookup = ProgressLookup()
        self.padding_margin = padding_margin
        self.check_programs()
        self.section_count = self.sqlController.get_section_count(self.animal)
        super().__init__(self.fileLocationManager.get_logdir())

    def get_chunk_size(self):  # for max resolution
        if self.downsample == True:
            return [256, 256, 1]
        else:
            return [3072, 3072, 1]

    @staticmethod
    def check_programs():
        """
        Make sure the necessary tools are installed on the machine and configures the memory of involving tools to work with
        big images.
        Some tools we use are based on java so we adjust the java heap size limit to 10 GB.  This is big enough for our purpose but should
        be increased accordingly if your images are bigger
        If the check failed, check the workernoshell.err.log in your project directory for more information
        """
        start_time = timer()
        os.environ["_JAVA_OPTIONS"] = "-Xmx10g"  # DEPRECATED - JUN-2022?
        os.environ[
            "export CV_IO_MAX_IMAGE_PIXELS"
        ] = "21474836480"  # DEPRECATED - JUN-2022?

        error = ""
        if not os.path.exists("/usr/local/share/bftools/showinf"):
            error += "showinf in bftools is not installed"
        if not os.path.exists("/usr/local/share/bftools/bfconvert"):
            error += "\nbfconvert in bftools is not installed"
        if not os.path.exists("/usr/bin/identify"):
            error += "\nImagemagick is not installed"
        if not which("java"):
            error += "\njava is not installed"

        if len(error) > 0:
            print(error)
            sys.exit()
        end_time = timer()
        total_elapsed_time = end_time - start_time
        print(f"Check programs took {round(total_elapsed_time,1)} seconds")

    def run_program_and_time(self, function, function_name):
        """utility to run a specific function and time it

        Args:
            function (function): funtion to run
            function_name (str): name of the function used to report timing result
        """
        print(function_name)
        start_time = timer()

        self.logevent("START " + str(function_name))
        if self.downsample == False and (
            function_name == "Creating normalization"
            or function_name == "Applying masks"
            or function_name == "Making histogram"
            or function_name == "Making combined histogram"
            or function_name == "Creating elastics transform"
        ):
            self.logevent(f"N/A - FULL RESOLUTION")
        if function_name == "Making downsampled copies":
            self.logevent(f"OUTPUT FOLDER: {self.fileLocationManager.thumbnail}")
        else:
            pass

        function()  # RUN FUNCTION

        end_time = timer()
        total_elapsed_time = end_time - start_time
        print(f"{function_name} took {round(total_elapsed_time,1)} seconds")

        sep = "*" * 40 + "\n"
        if function_name == "create web friendly image":
            ending_files = os.listdir(self.fileLocationManager.thumbnail_web)
            self.logevent(f"FILE COUNT: {len(ending_files)}\n{sep}")
        else:
            self.logevent(
                f"{function_name} took {round((end_time - start_time), 1)} seconds\n{sep}"
            )

    def prepare_image_for_quality_control(self):
        """This is the first step of the   The images are extracted from the CZI files,
        logged in the database, and downsampled to a web friendly size.  These preparations makes
        it possible to preview the images on the django database admin portal, allowing the user to
        perform quality control on the images.  The user can determine to mark slides or sections
        on a slide as insufficient in quality, and replace them with adjuscent slide or sections

        1) extract meta info
        2) extract tiffs from czi
        3) create png files (downsampled)
        """
        self.run_program_and_time(
            self.extract_slide_meta_data_and_insert_to_database, "Creating meta"
        )
        self.run_program_and_time(
            self.create_web_friendly_image, "create web friendly image"
        )
        self.run_program_and_time(self.extract_tifs_from_czi, "Extracting Tiffs")

    def apply_qc_and_prepare_image_masks(self):
        """This function performs 2 steps:
        1. Applies the QC result that the user provides on the Django database admin portal and prepares a copy
        of the tiff files that reflects the image/slide exclusion and replacement decisions made by user.
        Following steps in the pipeline then use this copy as the input
        2. Use a CNN based machine learning algorism to create masks around the tissue.
           These masks will be used to crop out the tissue from the surrounding debres.
        """
        self.run_program_and_time(self.apply_QC, "applying QC")
        self.set_task_preps()
        self.run_program_and_time(
            self.create_normalized_image, "Creating normalization"
        )
        self.run_program_and_time(self.create_mask, "Creating masks")

    def clean_images_and_create_histogram(self):
        """This function performs the following steps:
        1. apply the Edits of images masks made by user
        2. create the cleaned images using the image masks
        3. making a histogram of pixel intensity for view in the Django admin portal
        """
        self.run_program_and_time(self.apply_user_mask_edits, "Applying masks")
        self.run_program_and_time(self.create_cleaned_images, "Creating cleaned image")
        self.run_program_and_time(self.make_histogram, "Making histogram")
        self.run_program_and_time(
            self.make_combined_histogram, "Making combined histogram"
        )

    def align_images_within_stack(self):
        """This function calculates the rigid transformation used to align the images within stack and applies them to the image"""

        self.run_program_and_time(
            self.create_within_stack_transformations, "Creating elastix transform"
        )
        self.logevent("START get_transformations (PREREQUISITE FOR align_images)")
        start_time = timer()
        transformations = self.get_transformations()
        end_time = timer()
        total_elapsed_time = end_time - start_time
        print(f"'get_transformations' took {round(total_elapsed_time,1)} seconds")
        sep = "*" * 40 + "\n"

        print("START align_images")
        self.logevent("START align_images")
        start_time = timer()
        self.align_downsampled_images(transformations)
        self.align_full_size_image(transformations)
        end_time = timer()
        total_elapsed_time = end_time - start_time
        print(
            f"Creating elastix and alignment took {round(total_elapsed_time,1)} seconds"
        )
        sep = "*" * 40 + "\n"
        self.logevent(
            f"'align_images_within_stack' took {round((end_time - start_time), 1)} seconds\n{sep}"
        )

    def create_neuroglancer_cloud_volume(self):
        """This function creates the Seung lab neuroglancer cloud volume folders that is required to view the images in neuroglancer"""
        start_time = timer()
        self.run_program_and_time(self.create_neuroglancer, "Neuroglancer1 single")
        self.run_program_and_time(self.create_downsamples, "Neuroglancer2 pyramid")
        end_time = timer()
        total_elapsed_time = end_time - start_time
        print(
            f"Last step: creating neuroglancer images took {round(total_elapsed_time,1)} seconds"
        )
        sep = "*" * 40 + "\n"
        self.logevent(
            f"'create_neuroglancer_cloud_volume' took {round((end_time - start_time), 1)} seconds\n{sep}"
        )

    def qc_cleanup(self):
        """Post QC to clean up filesystem prior to re-running mask edits"""

        def background_del(org_path):
            try:
                basename = os.path.basename(os.path.normpath(org_path))
                new_path = os.path.join(org_path, "..", "." + str(basename))
                if os.path.exists(basename):
                    os.rename(org_path, new_path)
                    threading.Thread(target=lambda: shutil.rmtree(new_path)).start()
                else:
                    print(f"FOLDER ALREADY DELETED: {basename}")
            except OSError as e:
                print(f"FOLDER ALREADY DELETED: {new_path}")

        sep = "*" * 40 + "\n"
        msg = f"DELETE MASKED FILES FROM {self.fileLocationManager.thumbnail_masked}"
        self.logevent(f"{msg} \n{sep}")
        background_del(self.fileLocationManager.thumbnail_masked)


    def align_cleanup(self):
        """
        THIS STEP IS RE-RUN IMAGE ALIGNMENT:
        DELETE FOLDERS: 
        DELETE DB ENTRIES: 
        """

        def background_del(org_path):
            try:
                basename = os.path.basename(os.path.normpath(org_path))
                new_path = os.path.join(org_path, "..", "." + str(basename))
                if os.path.exists(basename):
                    os.rename(org_path, new_path)
                    threading.Thread(target=lambda: shutil.rmtree(new_path)).start()
                else:
                    print(f"FOLDER ALREADY DELETED: {basename}")
            except OSError as e:
                print(f"FOLDER ALREADY DELETED: {new_path}")

        sep = "*" * 40 + "\n"
        thumbnail_aligned_dir = self.fileLocationManager.get_thumbnail_aligned()
        msg = f"DELETE ALIGNED THUMBNAILS FILES FROM {thumbnail_aligned_dir}"
        self.logevent(f"{msg} \n{sep}")
        background_del(thumbnail_aligned_dir)

        thumbnail_cleaned_dir = self.fileLocationManager.get_thumbnail_cleaned()
        msg = f"DELETE CLEANED THUMBNAILS FILES FROM {thumbnail_cleaned_dir}"
        self.logevent(f"{msg} \n{sep}")
        background_del(thumbnail_cleaned_dir)


    def ng_cleanup(self, downsample, channel):
        """
        THIS STEP IS RE-RUN NEUROGLANCER:
        DELETE FOLDERS: neuroglancer_data
        DELETE DB ENTRIES: file_log
        """

        def background_del(org_path):
            try:
                basename = os.path.basename(os.path.normpath(org_path))
                new_path = os.path.join(org_path, "..", "." + str(basename))
                if os.path.exists(org_path):
                    os.rename(org_path, new_path)
                    dirname = os.path.dirname(org_path)
                    del_path = os.path.join(dirname, "." + str(basename))
                    threading.Thread(target=lambda: shutil.rmtree(del_path)).start()
                else:
                    print(f"FOLDER ALREADY DELETED: {basename}")
            except OSError as e:
                print(f"FOLDER ALREADY DELETED: {new_path}")

        sep = "*" * 40 + "\n"
        OUTPUT_DIR = self.fileLocationManager.get_neuroglancer(
            self.downsample, self.channel
        )
        msg = f"DELETE NEUROGLANCER FILES FROM {OUTPUT_DIR}"
        self.logevent(f"{msg} \n{sep}")
        print(msg)
        background_del(OUTPUT_DIR)

        # OUTPUT_DIR = self.fileLocationManager.get_neuroglancer("True", self.channel)
        # msg = f"DELETE NEUROGLANCER FILES FROM {OUTPUT_DIR}"
        # self.logevent(f"{msg} \n{sep}")
        # print(msg)
        # background_del(OUTPUT_DIR)

        db_output = self.sqlController.clear_file_log(
            self.animal, self.downsample, self.channel
        )

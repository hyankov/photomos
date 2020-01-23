"""
Description
--
Photomosaic module. Creates a mosaic based on a source photo,
from a library of photos.

Author
--
Hristo Yankov
"""

# System imports
import argparse
import glob
import math
import multiprocessing as mp
import os
import random
from argparse import Namespace
from typing import List, Tuple
from PIL import Image
from tqdm import tqdm, trange


class PhotoMosaic:
    """
    Description
    --
    Creates a mosaic based on a source photo, from a library of photos.
    """

    def _load_library_image(self, args) -> Tuple:
        """
        Description
        --
        Loads a library image, resizes it to the proper size and finds its
        dominant color.

        Parameters
        --
        - args - a tuple
            - img_path - the path to the image.
            - width - the width to which to resize the image.
            - height - the height to which to resize the image.

        Returns
        --
        Tuple of dominant color and properly sized library image that can replace it.
        """

        # Unpack the arguments
        library_image_path, width, height = args

        if not os.path.exists(library_image_path):
            raise ValueError("File '{}' does not exist".format(library_image_path))

        # Open the library image
        with Image.open(library_image_path) as lib_img:
            # Resize it to the size of a mosaic piece
            lib_img = lib_img.resize((width, height), Image.ANTIALIAS)

            # Get its average (dominant) color
            color = self._get_average_color(lib_img)

            return (color, lib_img)

    def _load_library(self, library_path: str, width: int, height: int) -> List:
        """
        Description
        --
        Loads the library files into a list.

        Parameters
        --
        - library_path - the path to the library.
        - width - the width to which to resize the image.
        - height - the height to which to resize the image.

        Returns
        --
        A list of tuples, where the first part is the dominant color and the second
        is the properly sized (as big as the mosaic piece) image.
        """

        if not library_path:
            raise ValueError("library_path is required")

        if not os.path.exists(library_path):
            raise ValueError("Folder '{}' does not exist".format(library_path))

        if not os.listdir(library_path):
            raise ValueError("Folder '{}' is empty".format(library_path))

        if width < 1:
            raise ValueError("width must be positive number")

        if height < 1:
            raise ValueError("height must be positive number")

        # TODO: Require minimum number of images?

        # TODO: Include other formats too.
        all_files = glob.glob(os.path.join(library_path, "*.jpg"))

        results = []

        # Parallel work with a progress bar
        with mp.Pool(mp.cpu_count()) as pool:
            for result in tqdm(
                    pool.imap_unordered(
                        self._load_library_image,
                        ((file, width, height) for file in all_files),
                        chunksize=10),
                    desc='Loading library',
                    total=len(all_files)):
                results.append(result)

        return results

    def _get_average_color(self, img: Image) -> Tuple:
        """
        Description
        --
        Gets the average (dominant) color of the image.

        Parameters
        --
        - img - the image.

        Returns
        --
        The dominant color (RGB).
        """

        if not img:
            raise ValueError("img is required")

        # Resize the image to 1px x 1px and get the pixel color.
        # That should be representing the dominant/average color for
        # the entire image.
        return img.resize((1, 1), Image.ANTIALIAS).getpixel((0, 0))

    def _get_closest_library_img(self, target_color: tuple, library: List) -> Image:
        """
        Description
        --
        Gets an image from the library that's closest to the color.

        Parameters
        --
        - target_color - the color, which we're searching a replacement
        image for.
        - library - the library of properly sized images.

        Returns
        --
        The library image that is closest to the color.
        """

        r, g, b = target_color
        distances = []

        # For each image in the library ...
        for lib_entry in library:
            lib_color, lib_image = lib_entry

            # Calculate the distance between the target color and the library image color
            cr, cg, cb = lib_color
            distance = math.sqrt(abs(r - cr)**2 + abs(g - cg)**2 + abs(b - cb)**2)

            # Add to the list of tuples (distance, library image)
            distances.append((distance, lib_image))

        sorted_distances = sorted(distances, key=lambda tup: tup[0])

        # TODO: Threshold of distances, pick random within the group. If no
        # appropriate image to replace with, replace with solid color?
        closest_image = sorted_distances[0]

        # Return the CLOSEST image
        return closest_image[1]

    def _create_mosaic_piece(self, args: tuple) -> Tuple:
        """
        Description
        --
        Gets the closest library image that can replace the piece
        of source image.

        Parameters
        --
        - args - the tupled parameters.
            - boxes - source and result box (coordinates).
            - source_image - the source image.
            - library - the library of images.

        Returns
        --
        A tuple of the replacement image and the coordinates on which it
        should be placed in the result image.
        """

        # Unpack the parameters
        boxes, source_image, library = args

        source_box = boxes['source_box']
        result_box = boxes['result_box']

        # Process a square of the source image
        piece_of_source_img = source_image.crop(source_box)

        # Get the average RGB of the image
        average_color = self._get_average_color(piece_of_source_img)

        # Get image from the library that's closest to the average color of the
        # piece of source image we're processing.
        replacement_image = self._get_closest_library_img(average_color, library)

        # Stitch the replacement into the original
        return (replacement_image, result_box)

    def _create_mosaic(self, args: Namespace) -> None:
        """
        Description
        --
        Creates the mosaic, based on command-line arguments.
        """

        # If source file was not provided, pick a random one from the library
        source_filename = args.source_filename
        if not source_filename:
            source_filename = random.choice(glob.glob(os.path.join(args.library, "*.jpg")))

        result_image = self.create_mosaic(source_filename, args.library, args.source_pixels, args.mosaic_pixels)

        # Save the result
        result_filename = "mosaic_{}".format(os.path.basename(source_filename))
        print("Saving output to '{}".format(result_filename))
        result_image.save(result_filename)

    def create_mosaic(self, source_filename: str, library_path: str, source_pixels: int, mosaic_pixels: int) -> None:
        """
        Description
        --
        Creates a mosaic image.

        Parameters
        --
        - source_filename - the filename of the source image.
        - library_path - the path to the folder containing the images.
        - source_pixels - the width of the sampling box for the source image.
        - mosaic_pixels - the width of the mosaic piece images.

        Returns
        --
        The mosaic image.
        """

        if not source_filename:
            raise ValueError("source_filename is required")

        if not os.path.exists(source_filename):
            raise ValueError("File '{}' does not exist".format(source_filename))

        if source_pixels < 10:
            raise ValueError("source_pixels cannot be less than 10")

        if mosaic_pixels < 10:
            raise ValueError("mosaic_pixels cannot be less than 10")

        with Image.open(source_filename) as source_image:
            source_width, source_height = source_image.size

            # X width is the level of details, Y height is keeping the ratio
            mosaic_width = mosaic_pixels

            # for Y, preserve the ratio of the source image
            # TODO: Need to take into consideration the dimensions of the mosaic
            # library image, or ratio could be skewed.
            mosaic_height = int((source_height / (source_width / mosaic_width)))

            # Load library into memory. The images are loaded in the size they'll be pasted into
            library = self._load_library(library_path, mosaic_width, mosaic_height)

            # Did we load anything?
            if not library:
                print("Library is empty, aborting ...")
                return None

            # Dimensions of sampling for the source image
            sample_width = source_pixels

            # for Y, preserve the ratio of the source image
            sample_height = int((source_height / (source_width / sample_width)))

            # Create the result image, as all-black
            result_image = Image.new(
                'RGB',
                (
                    int(mosaic_width * (source_width / sample_width)),
                    int(mosaic_height * (source_height / sample_height))
                ),
                (0, 0, 0))

            boxes = []
            for x_step in trange(source_width // sample_width, desc='Splitting source image'):
                for y_step in range(source_height // sample_height):
                    boxes.append({
                        'source_box': (
                            x_step * sample_width,
                            y_step * sample_height,
                            (x_step * sample_width) + sample_width - 1,
                            (y_step * sample_height) + sample_height - 1),

                        'result_box': (
                            x_step * mosaic_width,
                            y_step * mosaic_height)
                    })

            # In parallel, process multiple boxes at the same time, on all CPUs
            with mp.Pool(mp.cpu_count()) as pool:
                for result in tqdm(
                        pool.imap_unordered(
                            self._create_mosaic_piece,
                            ([box, source_image, library] for box in boxes),
                            chunksize=1000),
                        desc='Generating mosaic',
                        total=len(boxes)):

                    # Paste the replacement into the result image
                    replacement_image, result_box = result
                    result_image.paste(replacement_image, result_box)

            return result_image

    def get_args(self) -> Namespace:
        """
        Description
        --
        Gets the command line arguments.

        Returns
        --
        Namespace with the argument names and values.
        """

        parser = argparse.ArgumentParser("Photo mosaic", "Creates a mosaic from images.")

        parser.add_argument(
                                '-s',
                                '--source_filename',
                                help='The photo to create mosaic of. If not provided, will choose random\
                                from the library.')

        parser.add_argument(
                                '-spx',
                                '--source_pixels',
                                default=20,
                                type=int,
                                help='px width for source image sampling box (default: 20). Less\
                                    creates a bigger and more clearn mosaic.')

        parser.add_argument(
                                '-mpx',
                                '--mosaic_pixels',
                                default=85,
                                type=int,
                                help='px width of mosaic piece box (default: 85). More creates\
                                    bigger mosaic details, but will enlarge the result image.')

        parser.add_argument(
                                '-l',
                                '--library',
                                required=True,
                                help='The path to folder of photos to use to make the mosaic.')
        parser.set_defaults(func=self._create_mosaic)

        return parser.parse_args()


""" Entry point """
if __name__ == '__main__':
    photo_mosaic = PhotoMosaic()

    # Execute the command associated with the provided arguments.
    menu_args = photo_mosaic.get_args()
    menu_args.func(menu_args)

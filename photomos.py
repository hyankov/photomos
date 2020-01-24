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
from typing import Tuple
from PIL import Image
from tqdm import tqdm, trange


class Palette:
    """
    Description
    --
    Color and palette management.
    """

    def get_average_color(self, img: Image) -> Tuple:
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
        return img.resize((1, 1), Image.BICUBIC).getpixel((0, 0))


class Library:
    """
    Description
    --
    Handles the library of images to use as a mosaic.
    """

    def __init__(self, palette=Palette()):
        """
        Description
        --
        Initializes the instance.

        Parameters
        --
        - palette - the palette manager.
        """

        if not palette:
            raise ValueError("palette is required")

        self._palette = palette
        self._color_images = []

    def _load_image(self, args) -> Tuple:
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
        image_path, width, height = args

        if not os.path.exists(image_path):
            raise ValueError("File '{}' does not exist".format(image_path))

        # Open the library image
        try:
            with Image.open(image_path) as lib_img:
                # Resize it to the size of a mosaic piece
                lib_img = lib_img.resize((width, height), Image.BICUBIC)

                # Get its average (dominant) color
                color = self._palette.get_average_color(lib_img)

                return (color, lib_img)
        except Exception:
            # Could not load the file
            pass

    def load(self, folder_path: str, width: int, height: int) -> int:
        """
        Description
        --
        Loads the library files into a list.

        Parameters
        --
        - folder_path - the path to the library folder.
        - width - the width to which to resize the image.
        - height - the height to which to resize the image.

        Returns
        --
        The number of images loaded.
        """

        self._color_images = []

        if not folder_path:
            raise ValueError("folder_path is required")

        if not os.path.exists(folder_path):
            raise ValueError("Folder '{}' does not exist".format(folder_path))

        if not os.listdir(folder_path):
            raise ValueError("Folder '{}' is empty".format(folder_path))

        if width < 1:
            raise ValueError("width must be positive number")

        if height < 1:
            raise ValueError("height must be positive number")

        # TODO: Require minimum number of images?

        all_files = glob.glob(os.path.join(folder_path, "*.*"))

        # Parallel work with a progress bar
        with mp.Pool(mp.cpu_count()) as pool:
            for result in tqdm(
                    pool.imap_unordered(
                        self._load_image,
                        ((file, width, height) for file in all_files),
                        chunksize=5),
                    desc='Loading library',
                    total=len(all_files)):
                if result:
                    self._color_images.append(result)

        return len(self._color_images)

    def get_closest_image(self, target_color: tuple) -> Image:
        """
        Description
        --
        Gets an image from the library that's closest to the color.

        Parameters
        --
        - target_color - the color, which we're searching a replacement
        image for.

        Returns
        --
        The library image that is closest to the color.
        """

        r, g, b = target_color
        distances = []

        # For each image in the library ...
        for image in self._color_images:
            color, img = image

            # Calculate the distance between the target color and the library image color
            cr, cg, cb = color
            distance = math.sqrt(abs(r - cr)**2 + abs(g - cg)**2 + abs(b - cb)**2)

            # Add to the list of tuples (distance, library image)
            distances.append((distance, img))

        sorted_distances = sorted(distances, key=lambda tup: tup[0])

        # TODO: Threshold of distances, pick random within the group. If no
        # appropriate image to replace with, replace with solid color?
        closest_image = sorted_distances[0]

        # TODO: Threshold?
        # if closest_image[0] > 30:
        #   return None

        # Return the CLOSEST image
        return closest_image[1]


class PhotoMosaic:
    """
    Description
    --
    Creates a mosaic based on a source photo, from a library of photos.
    """

    def __init__(self, library=Library(), palette=Palette()) -> None:
        """
        Description
        --
        Initializes the instance.

        Parameters
        --
        - library - the library manager.
        - palette - the palette manager.
        """

        if not library:
            raise ValueError("library is required")

        if not palette:
            raise ValueError("palette is required")

        self._library = library
        self._palette = palette

    def _create_mosaic_piece(self, args: tuple) -> Tuple:
        """
        Description
        --
        Gets the closest library image that can replace the piece
        of source image.

        Parameters
        --
        - args - the tupled parameters.
            - coord - the coordinates.
            - source_image - the source image.
            - sample_width
            - sample_height
            - mosaic_width
            - mosaic_height

        Returns
        --
        A tuple of the replacement image and the coordinates on which it
        should be placed in the result image.
        """

        # Unpack the parameters
        coord, source_image, sample_width, sample_height, mosaic_width, mosaic_height = args

        # Process a square of the source image
        x, y = coord
        source_box = (
            x * sample_width,
            y * sample_height,
            (x * sample_width) + sample_width,
            (y * sample_height) + sample_height)
        piece_of_source_img = source_image.crop(source_box)

        # Get the average RGB of the image
        average_color = self._palette.get_average_color(piece_of_source_img)

        # Get image from the library that's closest to the average color of the
        # piece of source image we're processing.
        replacement_image = self._library.get_closest_image(average_color)

        if not replacement_image:
            # No replacement image was found, replace it with a solid color
            replacement_image = Image.new('RGB', (mosaic_width, mosaic_height), average_color)

        # Returns the image to replace the pixels at the coordinates.
        return (replacement_image, coord)

    def _create_mosaic(self, args: Namespace) -> None:
        """
        Description
        --
        Creates the mosaic, based on command-line arguments.

        Parameters
        --
        - args - the arguments.
        """

        # If source file was not provided, pick a random one from the library
        source_filename = args.source_filename
        if not source_filename:
            # TODO: Any eligible image actually
            source_filename = random.choice(glob.glob(os.path.join(args.library, "*.jpg")))

        result_image = self.create_mosaic(source_filename, args.library, args.source_pixels, args.mosaic_pixels)

        # Save the result
        result_filename = "mosaic_{}".format(os.path.basename(source_filename))
        print("Saving output to '{}".format(result_filename))
        result_image.save(result_filename)

    def create_mosaic(self, source_filename: str, library_path: str, spx: int, mpx: int) -> Image:
        """
        Description
        --
        Creates a mosaic image.

        Parameters
        --
        - source_filename - the filename of the source image.
        - library_path - the path to the folder containing the images.
        - spx - the width of the sampling box for the source image.
        - mpx - the width of the mosaic piece images.

        Returns
        --
        The mosaic image.
        """

        if not source_filename:
            raise ValueError("source_filename is required")

        if not os.path.exists(source_filename):
            raise ValueError("File '{}' does not exist".format(source_filename))

        if spx < 5:
            raise ValueError("spx cannot be less than 5")

        if mpx < 5:
            raise ValueError("mpx cannot be less than 5")

        with Image.open(source_filename) as source_image:
            source_width, source_height = source_image.size

            # The ratio of the source image
            ratio = source_width / source_height

            # Calculate dimensions, based on ratio
            # TODO: Need to take into consideration the dimensions of the mosaic
            # library image, or ratio could be skewed.
            mosaic_width = mpx
            mosaic_height = int(mosaic_width / ratio)
            sample_width = spx
            sample_height = int(sample_width / ratio)

            # Create the result image, as all-black
            result_image = Image.new(
                'RGB',
                (
                    int(source_width * (mosaic_width / sample_width)),
                    int(source_height * ((mosaic_width / ratio) / (sample_width / ratio)))
                ),
                (0, 0, 0))

            coordinates = []
            for x in trange(math.ceil(source_width / sample_width), desc='Partitioning source image'):
                for y in range(math.ceil(source_height / sample_height)):
                    coordinates.append((x, y))

            # Load library into memory. The images are loaded in the size they'll be pasted into
            count = self._library.load(library_path, mosaic_width, mosaic_height)

            # Did we load anything?
            if count == 0:
                print("Could not load any images, aborting ...")
                return None

            # In parallel, process multiple boxes at the same time, on all CPUs
            with mp.Pool(mp.cpu_count()) as pool:
                for result in tqdm(
                        pool.imap_unordered(
                            self._create_mosaic_piece,
                            ([coord, source_image, sample_width, sample_height, mosaic_width, mosaic_height] for coord in coordinates),
                            chunksize=1000),
                        desc='Generating mosaic',
                        total=len(coordinates)):

                    # Paste the replacement into the result image
                    replacement_image, coordinates = result
                    x, y = coordinates

                    result_image.paste(
                        replacement_image,
                        (
                            x * mosaic_width,
                            y * mosaic_height,
                            (x * mosaic_width) + mosaic_width,
                            (y * mosaic_height) + mosaic_height))

            return result_image

    def get_args(self) -> Namespace:
        """
        Description
        --
        Parses the command line arguments.

        Returns
        --
        Namespace with the argument names and values, as supplied
        by the command line.
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

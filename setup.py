from setuptools import setup, find_packages

setup(
    name="imessage-video-clipper",
    version="0.1.0",
    description="Split screen recordings of text message conversations into sequential, non-overlapping screenshots",
    python_requires=">=3.8",
    packages=find_packages(),
    install_requires=[
        "opencv-python>=4.5.0",
        "numpy>=1.20.0",
    ],
    entry_points={
        "console_scripts": [
            "imessage-video-clipper=imessage_video_clipper.cli:main",
        ],
    },
)

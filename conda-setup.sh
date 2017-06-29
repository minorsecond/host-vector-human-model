echo "Creating Conda environment 'HostVectorModel'"
conda create -y --name HostVectorModel python=3.4

echo "Activating environment and installing required modules"
source activate HostVectorModel
conda install -y numpy
conda install -y sqlalchemy
#conda install -y configparser
#conda install -y -c davidbgonzalez geoalchemy2=0.2.4
pip install geoalchemy2
pip install configparser
pip install psycopg2
pip install pyshp

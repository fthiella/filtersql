from setuptools import setup

def readme():
    with open('README.md') as f:
        return f.read()

setup(
        name='filtersql',
        version='0.5',
        description='SQL Backend Library for AI, Datatables and Frontend Apps',
        url='https://github.com/fthiella/filtersql',
        author='Federico Thiella',
        author_email='fthiella@gmail.com',
        license='MIT',
        packages=['filtersql'],
        zip_safe=False,
        include_package_data=True,
        long_description=readme(),
        long_description_content_type='text/markdown'
      )

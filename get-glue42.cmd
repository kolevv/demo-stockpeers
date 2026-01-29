@echo off
echo Downaloding glue-cli-lib package
curl "https://globalcdn.nuget.org/packages/glue-cli-lib.1.6.0.nupkg?packageVersion=1.6.0" --output "./glue-cli-lib.nupkg"
echo Downloading io.Connect.NET package
echo Unpacking glue-cli-lib package
tar -xf glue-cli-lib.nupkg glue-cli-lib
curl "https://globalcdn.nuget.org/packages/io.connect.net.1.27.0.nupkg" --output "./io.connect.NET.nupkg"
echo Unpacking io.connect.NET package
tar -xf io.connect.NET.nupkg lib/net45/

echo Updating local copies
rd /S /Q 32bit
move /Y glue-cli-lib\32bit . > nul
move /Y glue-cli-lib\*.dll . > nul
move /Y glue-cli-lib\*.pdb . > nul
move /Y glue-cli-lib\*.lib . > nul
move /Y glue-cli-lib\*.h . > nul
move /Y lib\net45\* . > nul
echo Cleaning up
del *.nupkg > nul
rd /S /Q lib
rd /S /Q glue-cli-lib
echo Done
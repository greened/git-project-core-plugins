REM SPDX-FileCopyrightText: 2023-present David A. Greene <dag@obbligato.org>

REM SPDX-License-Identifier: AGPL-3.0-or-later

REM Copyright 2023 David A. Greene

REM This file is part of git-project

REM git-project is free software: you can redistribute it and/or modify it under
REM the terms of the GNU Affero General Public License as published by the Free
REM Software Foundation, either version 3 of the License, or (at your option)
REM any later version.

REM This program is distributed in the hope that it will be useful, but WITHOUT
REM ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
REM FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for
REM more details.

REM You should have received a copy of the GNU Affero General Public License
REM along with git-project. If not, see <https://www.gnu.org/licenses/>.

@ECHO OFF

pushd %~dp0

REM Command file for Sphinx documentation

if "%SPHINXBUILD%" == "" (
	set SPHINXBUILD=sphinx-build
)
set SOURCEDIR=.
set BUILDDIR=_build

%SPHINXBUILD% >NUL 2>NUL
if errorlevel 9009 (
	echo.
	echo.The 'sphinx-build' command was not found. Make sure you have Sphinx
	echo.installed, then set the SPHINXBUILD environment variable to point
	echo.to the full path of the 'sphinx-build' executable. Alternatively you
	echo.may add the Sphinx directory to PATH.
	echo.
	echo.If you don't have Sphinx installed, grab it from
	echo.https://www.sphinx-doc.org/
	exit /b 1
)

if "%1" == "" goto help

%SPHINXBUILD% -M %1 %SOURCEDIR% %BUILDDIR% %SPHINXOPTS% %O%
goto end

:help
%SPHINXBUILD% -M help %SOURCEDIR% %BUILDDIR% %SPHINXOPTS% %O%

:end
popd

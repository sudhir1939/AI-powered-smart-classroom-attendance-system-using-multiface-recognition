@rem
@rem Copyright 2015 the original author or authors.
@rem
@rem Licensed under the Apache License, Version 2.0 (the "License");
@rem you may not use this file except in compliance with the License.
@rem You may obtain a copy of the License at
@rem
@rem      https://www.apache.org/licenses/LICENSE-2.0
@rem
@rem Unless required by applicable law or agreed to in writing, software
@rem distributed under the License is distributed on an "AS IS IS" BASIS,
@rem WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
@rem See the License for the specific language governing permissions and
@rem limitations under the License.
@rem
@if "%DEBUG%"=="" @echo off
@rem Set local scope for the current directory and the package to use.
set DIRNAME=%~dp0
if "%DIRNAME%"=="" set DIRNAME=.
set APP_BASE_NAME=%~n0
set APP_HOME=%DIRNAME%

@rem Find Java.
if defined JAVA_HOME goto findJavaFromJavaHome
set JAVA_EXE=java
%JAVA_EXE% -version >NUL 2>&1
if errorlevel 1 (
    echo ERROR: JAVA_HOME is not set and no 'java' could be found in your PATH.
    exit /b 1
)
:findJavaFromJavaHome
if exist "%JAVA_HOME%\bin\java.exe" goto init

echo ERROR: JAVA_HOME is set but does not point to a valid JDK.
exit /b 1

:init
set CLASSPATH=
if not exist "%APP_HOME%\gradle\wrapper\gradle-wrapper.jar" (
    echo ERROR: Gradle Wrapper JAR is missing.
    exit /b 1
)
"%JAVA_EXE%" -classpath "%APP_HOME%\gradle\wrapper\gradle-wrapper.jar" org.gradle.wrapper.GradleWrapperMain %*

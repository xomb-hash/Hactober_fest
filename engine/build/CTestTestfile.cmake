# CMake generated Testfile for 
# Source directory: C:/Users/dell/Desktop/Hactober_fest/engine
# Build directory: C:/Users/dell/Desktop/Hactober_fest/engine/build
# 
# This file includes the relevant testing commands required for 
# testing this directory and lists subdirectories to be tested as well.
if(CTEST_CONFIGURATION_TYPE MATCHES "^([Dd][Ee][Bb][Uu][Gg])$")
  add_test(alignment_unit_tests "C:/Users/dell/Desktop/Hactober_fest/engine/build/Debug/server.exe" "--test")
  set_tests_properties(alignment_unit_tests PROPERTIES  _BACKTRACE_TRIPLES "C:/Users/dell/Desktop/Hactober_fest/engine/CMakeLists.txt;91;add_test;C:/Users/dell/Desktop/Hactober_fest/engine/CMakeLists.txt;0;")
elseif(CTEST_CONFIGURATION_TYPE MATCHES "^([Rr][Ee][Ll][Ee][Aa][Ss][Ee])$")
  add_test(alignment_unit_tests "C:/Users/dell/Desktop/Hactober_fest/engine/build/Release/server.exe" "--test")
  set_tests_properties(alignment_unit_tests PROPERTIES  _BACKTRACE_TRIPLES "C:/Users/dell/Desktop/Hactober_fest/engine/CMakeLists.txt;91;add_test;C:/Users/dell/Desktop/Hactober_fest/engine/CMakeLists.txt;0;")
elseif(CTEST_CONFIGURATION_TYPE MATCHES "^([Mm][Ii][Nn][Ss][Ii][Zz][Ee][Rr][Ee][Ll])$")
  add_test(alignment_unit_tests "C:/Users/dell/Desktop/Hactober_fest/engine/build/MinSizeRel/server.exe" "--test")
  set_tests_properties(alignment_unit_tests PROPERTIES  _BACKTRACE_TRIPLES "C:/Users/dell/Desktop/Hactober_fest/engine/CMakeLists.txt;91;add_test;C:/Users/dell/Desktop/Hactober_fest/engine/CMakeLists.txt;0;")
elseif(CTEST_CONFIGURATION_TYPE MATCHES "^([Rr][Ee][Ll][Ww][Ii][Tt][Hh][Dd][Ee][Bb][Ii][Nn][Ff][Oo])$")
  add_test(alignment_unit_tests "C:/Users/dell/Desktop/Hactober_fest/engine/build/RelWithDebInfo/server.exe" "--test")
  set_tests_properties(alignment_unit_tests PROPERTIES  _BACKTRACE_TRIPLES "C:/Users/dell/Desktop/Hactober_fest/engine/CMakeLists.txt;91;add_test;C:/Users/dell/Desktop/Hactober_fest/engine/CMakeLists.txt;0;")
else()
  add_test(alignment_unit_tests NOT_AVAILABLE)
endif()

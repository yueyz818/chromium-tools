// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#ifndef TOOLS_JSON_SCHEMA_COMPILER_UTIL_H__
#define TOOLS_JSON_SCHEMA_COMPILER_UTIL_H__

#include <string>
#include <vector>

#include "base/memory/linked_ptr.h"
#include "base/memory/scoped_ptr.h"
#include "base/values.h"

namespace json_schema_compiler {

namespace util {

// Populates the item |out| from the value |from|. These are used by template
// specializations of |Get(Optional)ArrayFromList|.
bool PopulateItem(const base::Value& from, int* out);
bool PopulateItem(const base::Value& from, bool* out);
bool PopulateItem(const base::Value& from, double* out);
bool PopulateItem(const base::Value& from, std::string* out);
bool PopulateItem(const base::Value& from, std::vector<char>* out);
bool PopulateItem(const base::Value& from, linked_ptr<base::Value>* out);
bool PopulateItem(const base::Value& from,
                  linked_ptr<base::DictionaryValue>* out);

// This template is used for types generated by tools/json_schema_compiler.
template <class T>
bool PopulateItem(const base::Value& from, linked_ptr<T>* out) {
  const base::DictionaryValue* dict = nullptr;
  if (!from.GetAsDictionary(&dict))
    return false;
  scoped_ptr<T> obj(new T());
  if (!T::Populate(*dict, obj.get()))
    return false;
  *out = linked_ptr<T>(obj.release());
  return true;
}

// Populates |out| with |list|. Returns false if there is no list at the
// specified key or if the list has anything other than |T|.
template <class T>
bool PopulateArrayFromList(const base::ListValue& list, std::vector<T>* out) {
  out->clear();
  T item;
  for (const base::Value* value : list) {
    if (!PopulateItem(*value, &item))
      return false;
    out->push_back(item);
  }

  return true;
}

// Creates a new vector containing |list| at |out|. Returns
// true on success or if there is nothing at the specified key. Returns false
// if anything other than a list of |T| is at the specified key.
template <class T>
bool PopulateOptionalArrayFromList(const base::ListValue& list,
                                   scoped_ptr<std::vector<T>>* out) {
  out->reset(new std::vector<T>());
  if (!PopulateArrayFromList(list, out->get())) {
    out->reset();
    return false;
  }
  return true;
}

// Appends a Value newly created from |from| to |out|. These used by template
// specializations of |Set(Optional)ArrayToList|.
void AddItemToList(const int from, base::ListValue* out);
void AddItemToList(const bool from, base::ListValue* out);
void AddItemToList(const double from, base::ListValue* out);
void AddItemToList(const std::string& from, base::ListValue* out);
void AddItemToList(const std::vector<char>& from, base::ListValue* out);
void AddItemToList(const linked_ptr<base::Value>& from, base::ListValue* out);
void AddItemToList(const linked_ptr<base::DictionaryValue>& from,
                   base::ListValue* out);

// This template is used for types generated by tools/json_schema_compiler.
template <class T>
void AddItemToList(const linked_ptr<T>& from, base::ListValue* out) {
  out->Append(from->ToValue().release());
}

// Set |out| to the the contents of |from|. Requires PopulateItem to be
// implemented for |T|.
template <class T>
void PopulateListFromArray(const std::vector<T>& from, base::ListValue* out) {
  out->Clear();
  for (const auto& item : from)
    AddItemToList(item, out);
}

// Set |out| to the the contents of |from| if |from| is not null. Requires
// PopulateItem to be implemented for |T|.
template <class T>
void PopulateListFromOptionalArray(const scoped_ptr<std::vector<T>>& from,
                                   base::ListValue* out) {
  if (from.get())
    PopulateListFromArray(*from, out);
}

template <class T>
scoped_ptr<base::Value> CreateValueFromArray(const std::vector<T>& from) {
  base::ListValue* list = new base::ListValue();
  PopulateListFromArray(from, list);
  return scoped_ptr<base::Value>(list);
}

template <class T>
scoped_ptr<base::Value> CreateValueFromOptionalArray(
    const scoped_ptr<std::vector<T>>& from) {
  if (from.get())
    return CreateValueFromArray(*from);
  return scoped_ptr<base::Value>();
}

std::string ValueTypeToString(base::Value::Type type);

}  // namespace util
}  // namespace json_schema_compiler

#endif  // TOOLS_JSON_SCHEMA_COMPILER_UTIL_H__

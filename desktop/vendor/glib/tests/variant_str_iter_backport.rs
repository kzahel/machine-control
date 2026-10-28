use glib::variant::ToVariant;

#[test]
fn string_variant_iteration_survives_optimization() {
    let values = ["first", "", "Grüße", "last"];
    let variant = values.to_variant();
    assert_eq!(
        variant.array_iter_str().unwrap().collect::<Vec<_>>(),
        values
    );
    assert_eq!(
        variant.array_iter_str().unwrap().rev().collect::<Vec<_>>(),
        values.into_iter().rev().collect::<Vec<_>>()
    );

    let mut iter = variant.array_iter_str().unwrap();
    assert_eq!(iter.next(), Some("first"));
    assert_eq!(iter.next_back(), Some("last"));
    assert_eq!(iter.next_back(), Some("Grüße"));
    assert_eq!(iter.next(), Some(""));
    assert_eq!(iter.next(), None);
    assert_eq!(iter.next_back(), None);
}

#[test]
fn pointer_slice_retains_storage_after_dropping_elements() {
    let items = [
        glib::Error::new(glib::FileError::Failed, "first"),
        glib::Error::new(glib::FileError::Failed, "second"),
        glib::Error::new(glib::FileError::Failed, "third"),
    ];
    let mut slice = glib::PtrSlice::from(&items[..]);
    slice.truncate(1);
    assert_eq!(slice.len(), 1);
    assert_eq!(slice[0].message(), "first");
    slice.push(glib::Error::new(glib::FileError::Failed, "replacement"));
    assert_eq!(slice[1].message(), "replacement");
    slice.truncate(0);
    assert!(slice.is_empty());
    slice.push(glib::Error::new(glib::FileError::Failed, "reused"));
    assert_eq!(slice[0].message(), "reused");
    assert_eq!(items[2].message(), "third");
}
